#include "Starfall.h"

// Dialogue actions: when an INFO listed in forms.json "infoActions" finishes (TESTopicInfoEvent
// kTopicEnd; kTopicBegin with ActionOnTopicStart=1), apply its actions on the player/quest.
// Quest and inventory changes go through the Papyrus natives (SetCurrentStageID,
// SetObjectiveDisplayed, AddItem, RemoveItem, Lock) so the game shows its usual notifications
// and updates journal/markers exactly as a fragment script would.
// "once": true remembers the INFO in the cosave so the actions never run twice in a playthrough.

namespace SF::Dialogue
{
	namespace
	{
		void Apply(const InfoAction& a_act)
		{
			auto player = RE::PlayerCharacter::GetSingleton();
			if (!player) return;
			SKSE::log::info("dialogue: INFO {:08X} finished, applying actions", a_act.info);

			if (a_act.removeItem && a_act.removeItem->item) {
				// ObjectReference.RemoveItem(Form akItemToRemove, int aiCount = 1, bool abSilent = false, ObjectReference akOtherContainer = None)
				Papyrus::CallActor(player, "RemoveItem",
					RE::MakeFunctionArguments(static_cast<RE::TESForm*>(a_act.removeItem->item), static_cast<std::int32_t>(a_act.removeItem->count), false,
						static_cast<RE::TESObjectREFR*>(nullptr)));
			}
			if (a_act.addItem && a_act.addItem->item) {
				// ObjectReference.AddItem(Form akItemToAdd, int aiCount = 1, bool abSilent = false)
				Papyrus::CallActor(player, "AddItem",
					RE::MakeFunctionArguments(static_cast<RE::TESForm*>(a_act.addItem->item), static_cast<std::int32_t>(a_act.addItem->count), false));
			}
			if (a_act.faction && !player->IsInFaction(a_act.faction)) {
				player->AddToFaction(a_act.faction, a_act.factionRank);
			}
			for (auto id : a_act.unlock) {
				if (auto ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(id)) {
					// ObjectReference.Lock(bool abLock = true, bool abAsOwner = false): also refreshes the door/container state
					Papyrus::CallRef(ref, "Lock", RE::MakeFunctionArguments(false, false));
				}
			}
			for (auto id : a_act.enable) {
				if (auto ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(id); ref && ref->IsDisabled()) {
					ref->Enable(false);
				}
			}
			if (a_act.openVendor && data.vendorActor) {
				if (auto vendor = RE::TESForm::LookupByID<RE::Actor>(data.vendorActor)) {
					// Actor.ShowBarterMenu(): opens the vendor's buy/sell menu (needs the vendor faction on the NPC)
					Papyrus::CallActor(vendor, "ShowBarterMenu", RE::MakeFunctionArguments());
				}
			}
			if (data.quest) {
				for (int obj : a_act.objectivesCompleted) {
					// Quest.SetObjectiveCompleted(int aiObjective, bool abCompleted = true)
					Papyrus::CallQuest(data.quest, "SetObjectiveCompleted", RE::MakeFunctionArguments(static_cast<std::int32_t>(obj), true));
				}
				if (a_act.setStage) {
					// Quest.SetCurrentStageID(int aiStageID): starts the quest if needed, runs the stage fragment
					Papyrus::CallQuest(data.quest, "SetCurrentStageID", RE::MakeFunctionArguments(static_cast<std::int32_t>(*a_act.setStage)));
				}
				for (int obj : a_act.objectivesDisplayed) {
					// Quest.SetObjectiveDisplayed(int aiObjective, bool abDisplayed = true, bool abForce = false)
					Papyrus::CallQuest(data.quest, "SetObjectiveDisplayed", RE::MakeFunctionArguments(static_cast<std::int32_t>(obj), true, false));
				}
			} else if (a_act.setStage || !a_act.objectivesCompleted.empty() || !a_act.objectivesDisplayed.empty()) {
				SKSE::log::warn("dialogue: INFO {:08X} has quest actions but forms.json \"quest\" did not resolve", a_act.info);
			}
		}
	}

	void OnInfo(RE::FormID a_info)
	{
		auto it = data.infoActions.find(a_info);
		if (it == data.infoActions.end()) return;
		const auto& act = it->second;
		if (act.once) {
			if (fired.contains(a_info)) {
				SFDBG("dialogue: INFO {:08X} already applied (once)", a_info);
				return;
			}
			fired.insert(a_info);
		}
		Apply(act);
	}

	void Reset()
	{
		fired.clear();
	}

	namespace
	{
		class TopicInfoSink : public RE::BSTEventSink<RE::TESTopicInfoEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESTopicInfoEvent* a_event, RE::BSTEventSource<RE::TESTopicInfoEvent>*) override
			{
				if (!a_event || !gameReady) return RE::BSEventNotifyControl::kContinue;
				const auto want = cfg.actionOnTopicStart ? RE::TESTopicInfoEvent::TopicInfoEventType::kTopicBegin : RE::TESTopicInfoEvent::TopicInfoEventType::kTopicEnd;
				if (a_event->type.get() != want) return RE::BSEventNotifyControl::kContinue;
				const auto id = a_event->topicInfoFormID;
				// data.infoActions is read-only after kDataLoaded, so this lookup is safe off-thread
				if (data.infoActions.contains(id)) {
					SKSE::GetTaskInterface()->AddTask([id]() { OnInfo(id); });
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		static TopicInfoSink sink;
		if (auto holder = RE::ScriptEventSourceHolder::GetSingleton()) {
			holder->AddEventSink<RE::TESTopicInfoEvent>(&sink);
		}
	}
}
