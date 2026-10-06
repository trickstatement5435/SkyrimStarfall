#include "Starfall.h"

// Site presence + NPC to NPC chatter.
// The player's own cell-change event (BGSActorCellEvent, sent by PlayerCharacter) tells us when
// they enter or leave a site cell. While inside, the ticker calls Tick() a few times a second;
// Tick() re-checks the player's cell every 3 s as a safety net and drives the chatter state
// machine. Outside the site nothing runs.
//
// First entry: if the site quest is still at stage 0, it is set to 10 (DESIGN.md). No other
// quest is ever touched.

namespace SF::Site
{
	namespace
	{
		double nextCellCheck = 0.0;
		double nextChatter = 0.0;
		bool   inside = false;
		bool   pendingObjective = false;  // objective 10 waits until the quest is running
		std::unordered_map<std::size_t, double> lastPlayed;  // conversation index -> real time it ended

		struct Running
		{
			std::size_t     conv = 0;
			std::size_t     line = 0;
			double          nextLineAt = 0.0;
			RE::ActorHandle a;
			RE::ActorHandle b;
		};
		std::optional<Running> running;

		// "actors" entries may be a placed reference or a base NPC; for an NPC use whichever loaded
		// actor (high process = near the player) has that base.
		RE::Actor* FindActor(const std::string& a_edid)
		{
			auto it = data.actors.find(a_edid);
			if (it == data.actors.end() || !it->second) return nullptr;
			if (auto actor = it->second->As<RE::Actor>()) return actor;
			auto npc = it->second->As<RE::TESNPC>();
			auto pl = RE::ProcessLists::GetSingleton();
			if (!npc || !pl) return nullptr;
			RE::Actor* found = nullptr;
			pl->ForEachHighActor([&](RE::Actor* a_actor) {
				if (a_actor && a_actor->GetActorBase() == npc) {
					found = a_actor;
					return RE::BSContainer::ForEachResult::kStop;
				}
				return RE::BSContainer::ForEachResult::kContinue;
			});
			return found;
		}

		// in the dialogue menu with the player (speaker), or still finishing a line to them (lastSpeaker)
		bool EngagedByPlayer(RE::Actor* a_actor)
		{
			auto mtm = RE::MenuTopicManager::GetSingleton();
			if (!mtm || !a_actor || !mtm->menuOpen) return false;
			return mtm->speaker.get().get() == a_actor || mtm->lastSpeaker.get().get() == a_actor;
		}

		bool Available(RE::Actor* a_actor, RE::PlayerCharacter* a_player)
		{
			if (!a_actor || !a_actor->Is3DLoaded() || a_actor->IsDead() || a_actor->IsDisabled() || a_actor->IsInCombat()) return false;
			if (EngagedByPlayer(a_actor)) return false;
			return a_actor->GetPosition().GetDistance(a_player->GetPosition()) <= cfg.chatterPlayerDistance;
		}

		int QuestStage()
		{
			return data.quest ? static_cast<int>(data.quest->GetCurrentStageID()) : 0;
		}

		void SayLine(RE::Actor* a_speaker, RE::Actor* a_listener, RE::TESTopic* a_topic)
		{
			// Actor.SetLookAt(ObjectReference akTarget, bool abPathingLookAt = false)
			Papyrus::CallActor(a_speaker, "SetLookAt", RE::MakeFunctionArguments(static_cast<RE::TESObjectREFR*>(a_listener), false));
			Papyrus::CallActor(a_listener, "SetLookAt", RE::MakeFunctionArguments(static_cast<RE::TESObjectREFR*>(a_speaker), false));
			// ObjectReference.Say(Topic akTopicToSay, Actor akActorToSpeakAs = None, bool abSpeakInPlayersHead = false)
			Papyrus::CallActor(a_speaker, "Say", RE::MakeFunctionArguments(static_cast<RE::TESTopic*>(a_topic), static_cast<RE::Actor*>(nullptr), false));
		}

		void Finish(const char* a_why)
		{
			if (!running) return;
			for (auto h : { running->a, running->b }) {
				if (auto actor = h.get()) Papyrus::CallActor(actor.get(), "ClearLookAt", RE::MakeFunctionArguments());
			}
			SFDBG("chatter: conversation {} {}", running->conv, a_why);
			lastPlayed[running->conv] = RealNow();
			running.reset();
			nextChatter = RealNow() + cfg.chatterInterval * RandFloat(0.5f, 1.5f);
		}

		void TryStart(RE::PlayerCharacter* a_player)
		{
			const double now = RealNow();
			const int    stage = QuestStage();
			struct Cand
			{
				std::size_t idx;
				RE::Actor*  a;
				RE::Actor*  b;
				float       w;
			};
			std::vector<Cand> cands;
			float             total = 0.0f;
			for (std::size_t i = 0; i < data.conversations.size(); ++i) {
				auto& c = data.conversations[i];
				if (stage < c.minStage || stage > c.maxStage) continue;
				if (auto it = lastPlayed.find(i); it != lastPlayed.end() && now - it->second < cfg.conversationCooldown) continue;
				auto a = FindActor(c.a);
				auto b = FindActor(c.b);
				if (!a || !b || a == b || !Available(a, a_player) || !Available(b, a_player)) continue;
				if (a->GetPosition().GetDistance(b->GetPosition()) > cfg.chatterPairDistance) continue;
				cands.push_back({ i, a, b, c.weight });
				total += c.weight;
			}
			// try again soon-ish whether or not something started
			nextChatter = now + cfg.chatterInterval * RandFloat(0.5f, 1.5f);
			if (cands.empty() || total <= 0.0f) {
				SFDBG("chatter: no eligible conversation (stage {})", stage);
				return;
			}
			float r = RandFloat(0.0f, total);
			const Cand* pick = &cands.back();
			for (auto& c : cands) {
				r -= c.w;
				if (r <= 0.0f) {
					pick = &c;
					break;
				}
			}
			Running run;
			run.conv = pick->idx;
			run.line = 0;
			run.nextLineAt = now;
			run.a = pick->a->GetHandle();
			run.b = pick->b->GetHandle();
			running = run;
			SFDBG("chatter: starting conversation {} ({} / {})", pick->idx, data.conversations[pick->idx].a, data.conversations[pick->idx].b);
		}

		void Step(RE::PlayerCharacter* a_player)
		{
			auto a = running->a.get();
			auto b = running->b.get();
			if (!a || !b) return Finish("aborted: actor gone");
			const bool ok = a->Is3DLoaded() && b->Is3DLoaded() && !a->IsDead() && !b->IsDead();
			if (!ok) return Finish("aborted: actor unloaded or dead");
			if (a->IsInCombat() || b->IsInCombat()) return Finish("aborted: combat");
			if (EngagedByPlayer(a.get()) || EngagedByPlayer(b.get())) return Finish("aborted: player engaged");
			if (a->GetPosition().GetDistance(b->GetPosition()) > cfg.chatterPairDistance * 1.5f) return Finish("aborted: walked apart");
			if (a->GetPosition().GetDistance(a_player->GetPosition()) > cfg.chatterPlayerDistance * 1.5f) return Finish("aborted: player left");

			const double now = RealNow();
			if (now < running->nextLineAt) return;
			auto& conv = data.conversations[running->conv];
			if (running->line >= conv.lines.size()) return Finish("finished");
			auto& line = conv.lines[running->line];
			auto  speaker = line.speakerIsA ? a.get() : b.get();
			auto  listener = line.speakerIsA ? b.get() : a.get();
			SayLine(speaker, listener, line.topic);
			running->nextLineAt = now + line.seconds;
			++running->line;
		}

		void Enter()
		{
			inside = true;
			active = true;
			nextChatter = RealNow() + cfg.chatterInterval * RandFloat(0.25f, 0.75f);
			SKSE::log::info("site: player entered the Starfall site");
			// DESIGN.md: stage 10 "Speak with Director Kast" is set on first entering the site
			// The quest only starts while the player carries the Zero-Point device (the Gravity Gun).
			bool hasDevice = !data.gateItem;
			if (auto player = RE::PlayerCharacter::GetSingleton(); player && data.gateItem) {
				auto inv = player->GetInventoryCounts([](RE::TESBoundObject& a_obj) { return &a_obj == data.gateItem; });
				for (auto& [obj, count] : inv) hasDevice = hasDevice || count > 0;
			}
			if (data.quest && data.quest->GetCurrentStageID() == 0 && hasDevice) {
				SKSE::log::info("site: quest at stage 0 -> SetCurrentStageID(10)");
				Papyrus::CallQuest(data.quest, "SetCurrentStageID", RE::MakeFunctionArguments(static_cast<std::int32_t>(10)));
				pendingObjective = true;  // shown from Tick() once the quest is actually running (starting is asynchronous)
			}
		}

		void Leave()
		{
			Finish("aborted: player left the site");
			inside = false;
			active = false;
			SKSE::log::info("site: player left the Starfall site");
		}
	}

	void OnPlayerCellChanged()
	{
		auto player = RE::PlayerCharacter::GetSingleton();
		const bool now = player && IsSiteCell(player->GetParentCell());
		if (now && !inside) Enter();
		else if (!now && inside) Leave();
		nextCellCheck = RealNow() + 3.0;
	}

	void Tick()
	{
		if (!inside) return;
		auto player = RE::PlayerCharacter::GetSingleton();
		if (!player) return;
		if (RealNow() >= nextCellCheck) {
			OnPlayerCellChanged();
			if (!inside) return;
		}
		if (pendingObjective && data.quest && data.quest->IsRunning()) {
			pendingObjective = false;
			Papyrus::CallQuest(data.quest, "SetObjectiveDisplayed", RE::MakeFunctionArguments(static_cast<std::int32_t>(10), true, false));
		}
		if (!cfg.enableChatter || data.conversations.empty()) return;
		if (running) {
			Step(player);
		} else if (RealNow() >= nextChatter) {
			TryStart(player);
		}
	}

	void Reset()
	{
		running.reset();
		inside = false;
		active = false;
		lastPlayed.clear();
		nextChatter = 0.0;
		nextCellCheck = 0.0;
	}

	namespace
	{
		// PlayerCharacter is the only source of BGSActorCellEvent we listen to
		class PlayerCellSink : public RE::BSTEventSink<RE::BGSActorCellEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::BGSActorCellEvent* a_event, RE::BSTEventSource<RE::BGSActorCellEvent>*) override
			{
				if (a_event && gameReady && a_event->flags.get() == RE::BGSActorCellEvent::CellFlag::kEnter) {
					const auto cell = a_event->cellID;
					SKSE::GetTaskInterface()->AddTask([cell]() {
						OnPlayerCellChanged();
						Spawner::OnPlayerCellChanged(cell);
					});
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		static PlayerCellSink sink;
		static bool           done = false;
		if (done) return;
		auto player = RE::PlayerCharacter::GetSingleton();
		auto src = player ? player->AsBGSActorCellEventSource() : nullptr;
		if (src) {
			src->AddEventSink(&sink);
			done = true;
		}
	}
}
