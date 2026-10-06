#include "Starfall.h"

// Checkpoint gate in Skyrim.
// The gate group (bunker, door, sign, lights, barriers, map marker, sentry) is stored in the ESP as persistent
// references parked under the map. On every load this module moves the group next to its anchor (the vanilla
// Embershard Mine map marker + an offset, or absolute GateX/GateY from StarfallSite.ini) and, once the cell around
// the gate is loaded, snaps each piece onto the terrain. The door stays locked unless the player carries the
// Zero-Point device (Gravity Gun). Moving the gate also re-aims the crater-side door so it lands you in front of it.

namespace SF::Gate
{
	namespace
	{
		bool       placedSnapped = false;
		RE::NiPoint3 gateBase{};
		float        gateFacingDeg = 0.0f;

		bool Resolve(RE::NiPoint3& a_base, float& a_facing)
		{
			if (cfg.gateX != 0.0f || cfg.gateY != 0.0f) {
				a_base = { cfg.gateX, cfg.gateY, cfg.gateZ };
				a_facing = cfg.gateAngle;
				return true;
			}
			auto anchor = data.gateAnchor ? RE::TESForm::LookupByID<RE::TESObjectREFR>(data.gateAnchor) : nullptr;
			if (!anchor) return false;
			const float ox = std::isnan(cfg.gateOffsetX) ? data.gateOffX : cfg.gateOffsetX;
			const float oy = std::isnan(cfg.gateOffsetY) ? data.gateOffY : cfg.gateOffsetY;
			const auto  pos = anchor->GetPosition();
			a_base = { pos.x + ox, pos.y + oy, pos.z };
			a_facing = cfg.gateAngle != 0.0f ? cfg.gateAngle : data.gateFacing;
			return true;
		}

		float GroundZ(float a_x, float a_y, float a_fallback, bool& a_ok)
		{
			a_ok = false;
			auto tes = RE::TES::GetSingleton();
			if (!tes) return a_fallback;
			float h = 0.0f;
			if (tes->GetLandHeight(RE::NiPoint3{ a_x, a_y, a_fallback + 2000.0f }, h)) {
				a_ok = true;
				return h;
			}
			return a_fallback;
		}

		void Move(RE::TESObjectREFR* a_ref, const RE::NiPoint3& a_pos, float a_angleDeg)
		{
			// ObjectReference.SetPosition / SetAngle work on unloaded persistent references too
			float x = a_pos.x, y = a_pos.y, z = a_pos.z, ax = 0.0f, ay = 0.0f, az = a_angleDeg;
			Papyrus::CallRef(a_ref, "SetPosition", RE::MakeFunctionArguments(std::move(x), std::move(y), std::move(z)));
			Papyrus::CallRef(a_ref, "SetAngle", RE::MakeFunctionArguments(std::move(ax), std::move(ay), std::move(az)));
		}

		bool HasDevice()
		{
			auto player = RE::PlayerCharacter::GetSingleton();
			if (!player || !data.gateItem) return true;
			auto inv = player->GetInventoryCounts([](RE::TESBoundObject& a_obj) { return &a_obj == data.gateItem; });
			for (auto& [obj, count] : inv) {
				if (count > 0) return true;
			}
			return false;
		}
	}

	bool IsGateRef(RE::FormID a_id)
	{
		for (auto& g : data.gateRefs) {
			if (g.id == a_id) return true;
		}
		return false;
	}

	void Place(bool a_snap)
	{
		if (data.gateRefs.empty()) return;
		RE::NiPoint3 base;
		float        facing = 0.0f;
		if (!Resolve(base, facing)) {
			SKSE::log::warn("gate: anchor not found, gate stays parked");
			return;
		}
		const float rad = facing * std::numbers::pi_v<float> / 180.0f;
		const float c = std::cos(rad), s = std::sin(rad);
		bool  allSnapped = true;
		float doorZ = base.z;
		for (auto& g : data.gateRefs) {
			auto ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(g.id);
			if (!ref) continue;
			// door space: +Y = the way the door faces; rotate clockwise by the facing angle (Skyrim heading)
			const float x = base.x + g.dx * c + g.dy * s;
			const float y = base.y - g.dx * s + g.dy * c;
			float       z = base.z;
			const auto  cur = ref->GetPosition();
			const bool  alreadyHere = std::abs(cur.x - x) < 2.0f && std::abs(cur.y - y) < 2.0f;
			if (cfg.gateZ != 0.0f && (cfg.gateX != 0.0f || cfg.gateY != 0.0f)) {
				z = cfg.gateZ;
			} else {
				bool ok = false;
				if (a_snap) z = GroundZ(x, y, base.z, ok);
				if (!ok) {
					// land not loaded: keep the height from an earlier snap (saved with the reference)
					if (alreadyHere) z = cur.z - g.dz;
					allSnapped = false;
				}
			}
			if (g.door) doorZ = z;
			Move(ref, { x, y, z + g.dz }, facing + g.angle);
		}
		gateBase = { base.x, base.y, doorZ };
		gateFacingDeg = facing;
		placedSnapped = allSnapped;
		// the crater-side door teleports you in front of the gate door
		if (auto arrival = data.arrivalDoor ? RE::TESForm::LookupByID<RE::TESObjectREFR>(data.arrivalDoor) : nullptr) {
			if (auto tele = arrival->extraList.GetByType<RE::ExtraTeleport>(); tele && tele->teleportData) {
				tele->teleportData->position = { base.x + 140.0f * s, base.y + 140.0f * c, doorZ + 16.0f };
				tele->teleportData->rotation = { 0.0f, 0.0f, rad };
			}
		}
		SKSE::log::info("gate: placed at ({:.0f}, {:.0f}, {:.0f}) facing {:.0f}, snapped {}", base.x, base.y, doorZ, facing, allSnapped);
	}

	void UpdateLock()
	{
		auto door = data.gateDoor ? RE::TESForm::LookupByID<RE::TESObjectREFR>(data.gateDoor) : nullptr;
		if (!door) return;
		const bool lock = cfg.requireDevice && !HasDevice();
		if (door->IsLocked() != lock) {
			// ObjectReference.Lock(bool abLock, bool abAsOwner)
			bool l = lock, owner = false;
			Papyrus::CallRef(door, "Lock", RE::MakeFunctionArguments(std::move(l), std::move(owner)));
			SFDBG("gate: door {}", lock ? "locked" : "unlocked");
		}
	}

	namespace
	{
		class AttachSink : public RE::BSTEventSink<RE::TESCellAttachDetachEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESCellAttachDetachEvent* a_event, RE::BSTEventSource<RE::TESCellAttachDetachEvent>*) override
			{
				if (!a_event || !a_event->attached || !a_event->reference || !gameReady) return RE::BSEventNotifyControl::kContinue;
				const auto id = a_event->reference->GetFormID();
				if (id == data.gateDoor) {
					SKSE::GetTaskInterface()->AddTask([]() {
						Place(true);
						UpdateLock();
					});
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		class ContainerSink : public RE::BSTEventSink<RE::TESContainerChangedEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESContainerChangedEvent* a_event, RE::BSTEventSource<RE::TESContainerChangedEvent>*) override
			{
				if (!a_event || !gameReady || !data.gateItem || a_event->baseObj != data.gateItem->GetFormID()) return RE::BSEventNotifyControl::kContinue;
				constexpr RE::FormID kPlayer = 0x14;
				if (a_event->oldContainer == kPlayer || a_event->newContainer == kPlayer) {
					SKSE::GetTaskInterface()->AddTask([]() { UpdateLock(); });
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		class ActivateSink : public RE::BSTEventSink<RE::TESActivateEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESActivateEvent* a_event, RE::BSTEventSource<RE::TESActivateEvent>*) override
			{
				if (!a_event || !gameReady || !a_event->objectActivated || !a_event->actionRef) return RE::BSEventNotifyControl::kContinue;
				if (a_event->objectActivated->GetFormID() != data.gateDoor || !a_event->actionRef->IsPlayerRef()) return RE::BSEventNotifyControl::kContinue;
				SKSE::GetTaskInterface()->AddTask([]() {
					auto door = RE::TESForm::LookupByID<RE::TESObjectREFR>(data.gateDoor);
					if (door && door->IsLocked() && !data.gateDenied.empty()) Papyrus::Notify(data.gateDenied);
				});
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		static AttachSink    attach;
		static ContainerSink container;
		static ActivateSink  activate;
		if (auto holder = RE::ScriptEventSourceHolder::GetSingleton()) {
			holder->AddEventSink<RE::TESCellAttachDetachEvent>(&attach);
			holder->AddEventSink<RE::TESContainerChangedEvent>(&container);
			holder->AddEventSink<RE::TESActivateEvent>(&activate);
		}
	}
}
