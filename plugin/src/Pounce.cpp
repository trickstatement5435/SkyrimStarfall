#include "Starfall.h"

// Headcrab pounce (experimental, EnablePounce=1).
// TESCombatEvent tells us when a headcrab (actor or race carrying forms.json "headcrabKeyword")
// enters or leaves combat. While at least one is fighting, the ticker calls Tick() every 0.25 s.
// A crab on the ground with its target 120..480 units away (and off cooldown) is launched:
//   1. turn it to face the target,
//   2. send its behaviour graph an attack event (best guess "attackStart", INI PounceAnimEvent),
//   3. put its character controller into the in-air state and give it a velocity toward the
//      target plus an upward component.
// Havok expects metres-ish units, so game units/s are multiplied by bhkWorld::GetWorldScale(),
// the same conversion GravityGun uses for rigid bodies.
//
// Engine caveat (why the state is forced): while a character is kOnGround its controller velocity
// is recomputed from the animation's root motion every physics step, so a plain
// SetLinearVelocityImpl is mostly overwritten. Marking the controller kInAir/kJumping (and
// resetting the fall bookkeeping so landing doesn't apply fall damage from the jump height) lets
// Havok integrate the launch velocity under gravity until it lands. This mirrors what community
// jump/launch plugins do, but has not been verified on skeever-race actors.

namespace SF::Pounce
{
	namespace
	{
		struct Crab
		{
			RE::ActorHandle handle;
			double          nextPounce = 0.0;
		};
		std::unordered_map<RE::FormID, Crab> crabs;

		bool IsHeadcrab(RE::Actor* a_actor)
		{
			if (!a_actor || !data.headcrabKeyword) return false;
			if (a_actor->HasKeyword(data.headcrabKeyword)) return true;
			auto race = a_actor->GetRace();
			return race && race->HasKeyword(data.headcrabKeyword);
		}

		void Sync() { activeCount = static_cast<int>(crabs.size()); }

		bool TryPounce(RE::Actor* a_crab, Crab& a_state, double a_now)
		{
			if (a_now < a_state.nextPounce) return false;
			auto target = a_crab->GetActorRuntimeData().currentCombatTarget.get();
			if (!target || target->IsDead() || !target->Is3DLoaded()) return false;

			const auto from = a_crab->GetPosition();
			const auto to = target->GetPosition();
			const float dx = to.x - from.x, dy = to.y - from.y;
			const float horiz = std::sqrt(dx * dx + dy * dy);
			if (horiz < cfg.pounceMinRange || horiz > cfg.pounceMaxRange) return false;
			if (std::abs(to.z - from.z) > cfg.pounceMaxRange) return false;  // target on a different floor

			auto controller = a_crab->GetCharController();
			if (!controller) return false;
			if (controller->context.currentState != RE::hkpCharacterStateType::kOnGround || a_crab->IsInMidair()) return false;

			// 1. face the target (heading 0 = +Y, clockwise)
			const auto ang = a_crab->GetAngle();
			a_crab->SetAngle(RE::NiPoint3(ang.x, ang.y, std::atan2(dx, dy)));

			// 2. attack animation; returns false if the graph doesn't know the event (harmless)
			const bool animOk = !cfg.pounceAnimEvent.empty() && a_crab->NotifyAnimationGraph(cfg.pounceAnimEvent.c_str());

			// 3. launch
			const float s = RE::bhkWorld::GetWorldScale();
			const float nx = dx / horiz, ny = dy / horiz;
			const RE::hkVector4 vel(nx * cfg.pounceSpeed * s, ny * cfg.pounceSpeed * s, cfg.pounceUp * s, 0.0f);
			controller->flags.set(RE::CHARACTER_FLAGS::kJumping);
			controller->context.currentState = RE::hkpCharacterStateType::kInAir;
			controller->fallStartHeight = from.z;
			controller->fallTime = 0.0f;
			controller->SetLinearVelocityImpl(vel);

			a_state.nextPounce = a_now + cfg.pounceCooldown;
			SFDBG("pounce: {:08X} -> {:08X} at {:.0f} units (anim event {})", a_crab->GetFormID(), target->GetFormID(), horiz, animOk ? "accepted" : "ignored");
			return true;
		}
	}

	void OnCombat(RE::FormID a_actor, bool a_inCombat)
	{
		if (!cfg.enablePounce || !data.headcrabKeyword) return;
		auto actor = RE::TESForm::LookupByID<RE::Actor>(a_actor);
		if (!actor || !IsHeadcrab(actor)) return;
		if (a_inCombat) {
			auto& c = crabs[a_actor];
			c.handle = actor->GetHandle();
			// small grace period so it doesn't leap the instant it notices you
			c.nextPounce = std::max(c.nextPounce, RealNow() + 0.75);
		} else {
			crabs.erase(a_actor);
		}
		Sync();
	}

	void Tick()
	{
		if (crabs.empty()) return;
		const double now = RealNow();
		for (auto it = crabs.begin(); it != crabs.end();) {
			auto actor = it->second.handle.get();
			if (!actor || actor->IsDead() || !actor->Is3DLoaded() || !actor->IsInCombat() || actor->IsDisabled()) {
				it = crabs.erase(it);
				continue;
			}
			TryPounce(actor.get(), it->second, now);
			++it;
		}
		Sync();
	}

	void Reset()
	{
		crabs.clear();
		Sync();
	}

	namespace
	{
		class CombatSink : public RE::BSTEventSink<RE::TESCombatEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESCombatEvent* a_event, RE::BSTEventSource<RE::TESCombatEvent>*) override
			{
				if (a_event && a_event->actor && gameReady && cfg.enablePounce && data.headcrabKeyword) {
					const auto id = a_event->actor->GetFormID();
					const bool fighting = a_event->newState.get() == RE::ACTOR_COMBAT_STATE::kCombat;
					SKSE::GetTaskInterface()->AddTask([id, fighting]() { OnCombat(id, fighting); });
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		static CombatSink sink;
		if (auto holder = RE::ScriptEventSourceHolder::GetSingleton()) {
			holder->AddEventSink<RE::TESCombatEvent>(&sink);
		}
	}
}
