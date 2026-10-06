#include "Starfall.h"

// World spawner: occasionally drops a group from forms.json "spawner.groups" near the player
// when they arrive somewhere suitable. Purely event driven: cell load events queue an evaluation
// a couple of seconds later (via the ticker), so there is no per-frame work.
//
// Why TESCellFullyLoadedEvent: TESCellAttachDetachEvent is sent once per *reference* (hundreds
// per cell, possibly before the cell finished loading its refs), while TESCellFullyLoadedEvent
// is sent once per cell after all of its references exist, which is exactly when anchors can be
// enumerated. It can be missed when an interior comes back from the cell buffer, so the player's
// own cell-change event (BGSActorCellEvent) queues an evaluation too. Re-rolling the same cell is
// limited by RerollCooldownHours, so the two triggers never double the chance.
// TESCellAttachDetachEvent is still used, but only for its "detached" half: to clean up our own
// spawned references when their cell unloads.

namespace SF::Spawner
{
	namespace
	{
		// Vanilla Skyrim.esm location keywords (FormIDs from vanilla/formids.json).
		// Cells (or their parent locations) with any of these never spawn.
		constexpr RE::FormID kSkipKeywords[] = {
			0x039793,  // LocTypeHabitation
			0x013168,  // LocTypeCity
			0x013166,  // LocTypeTown
			0x01CB87,  // LocTypeInn
			0x0FC1A3,  // LocTypePlayerHouse
			// extra settled places, same idea
			0x013167,  // LocTypeSettlement
			0x0A6E84,  // LocTypeHabitationHasInn
			0x0130DC,  // LocTypeDwelling
			0x01CB85,  // LocTypeHouse
			0x01CB86,  // LocTypeStore
			0x01CD57,  // LocTypeCastle
			0x01CD56,  // LocTypeTemple
			0x01CD59,  // LocTypeJail
			0x01CD5A,  // LocTypeGuild
			0x01CD55,  // LocTypeBarracks
			0x018EF0,  // LocTypeFarm
			0x0130E9,  // LocTypeOrcStronghold
			0x0504F9,  // LocTypeStewardsDwelling
		};

		// Interiors only qualify when their location has one of these.
		// Note: Skyrim.esm has no LocTypeCave or LocTypeNordicRuin keyword. Caves carry
		// LocTypeDungeon (+ AnimalDen/BanditCamp...), Nordic ruins carry LocTypeDraugrCrypt.
		constexpr RE::FormID kDungeonKeywords[] = {
			0x0130DB,  // LocTypeDungeon
			0x0130E3,  // LocTypeDwarvenAutomatons
			0x0130E2,  // LocTypeDraugrCrypt (stands in for "LocTypeNordicRuin")
			0x018EF1,  // LocTypeMine
			0x0130DE,  // LocTypeAnimalDen
			0x0130DF,  // LocTypeBanditCamp
			0x0130E4,  // LocTypeFalmerHive
			0x0130EE,  // LocTypeForswornCamp
			0x0130EC,  // LocTypeWarlockLair
			0x0130EB,  // LocTypeVampireLair
			0x01929F,  // LocTypeShipwreck
		};

		constexpr RE::FormID kXMarker = 0x00003B;         // XMarker
		constexpr RE::FormID kXMarkerHeading = 0x000034;  // XMarkerHeading

		std::mutex                     idsLock;
		std::unordered_set<RE::FormID> trackedIds;  // mirror of `tracked` for lock-protected lookups from any thread

		std::unordered_set<RE::FormID>        pending;  // cells loaded since the last evaluation
		std::unordered_map<RE::FormID, float> rolled;   // roll key -> game hours of the last roll (runtime only)

		bool LocationHasAny(const RE::BGSLocation* a_loc, std::span<const RE::FormID> a_keywords, bool a_walkParents)
		{
			int depth = 0;
			for (auto loc = a_loc; loc && depth < 10; loc = a_walkParents ? loc->parentLoc : nullptr, ++depth) {
				for (auto kw : a_keywords) {
					if (loc->HasKeywordID(kw)) return true;
				}
			}
			return false;
		}

		// A parent location like "Riften" makes "Ratway" a city cell; a hold parent does not skip anything.
		bool IsSettled(const RE::BGSLocation* a_loc) { return LocationHasAny(a_loc, kSkipKeywords, true); }

		bool InteriorQualifies(RE::TESObjectCELL* a_cell)
		{
			auto loc = a_cell->GetLocation();
			if (!loc) {
				SFDBG("spawner: interior {:08X} has no location, skipped", a_cell->GetFormID());
				return false;
			}
			if (IsSettled(loc)) {
				SFDBG("spawner: interior {:08X} ({}) is a settled place, skipped", a_cell->GetFormID(), loc->GetName());
				return false;
			}
			if (!LocationHasAny(loc, kDungeonKeywords, false)) {
				SFDBG("spawner: interior {:08X} ({}) is not a dungeon/cave/mine/den/camp, skipped", a_cell->GetFormID(), loc->GetName());
				return false;
			}
			return true;
		}

		bool ExteriorCellQualifies(RE::TESObjectCELL* a_cell)
		{
			if (!a_cell || !a_cell->IsExteriorCell() || !a_cell->IsAttached() || IsSiteCell(a_cell)) return false;
			return !IsSettled(a_cell->GetLocation());
		}

		void AddTracked(const Tracked& a_t)
		{
			tracked.push_back(a_t);
			std::scoped_lock l{ idsLock };
			trackedIds.insert(a_t.id);
		}

		void EraseTracked(RE::FormID a_id)
		{
			std::erase_if(tracked, [&](const Tracked& t) { return t.id == a_id; });
			std::scoped_lock l{ idsLock };
			trackedIds.erase(a_id);
		}

		void RemoveRef(RE::TESObjectREFR* a_ref, const char* a_why)
		{
			if (!a_ref) return;
			SFDBG("spawner: removing {:08X} ({})", a_ref->GetFormID(), a_why);
			// Disable first so it vanishes cleanly, then flag it for deletion; the engine purges
			// deleted created refs when it saves/unloads.
			if (!a_ref->IsDisabled()) a_ref->Disable();
			a_ref->SetDelete(true);
		}

		bool IsAnchorBase(const RE::TESBoundObject* a_base)
		{
			if (!a_base) return false;
			switch (a_base->GetFormType()) {
			case RE::FormType::Container:
			case RE::FormType::Furniture:
			case RE::FormType::IdleMarker:
				return true;
			case RE::FormType::Static:
				return a_base->GetFormID() == kXMarker || a_base->GetFormID() == kXMarkerHeading;
			default:
				return false;
			}
		}

		struct Anchor
		{
			RE::TESObjectREFR* ref = nullptr;
			bool               inView = false;
		};

		void ConsiderAnchor(RE::TESObjectREFR* a_ref, RE::PlayerCharacter* a_player, std::vector<Anchor>& a_out, bool a_exterior)
		{
			if (!a_ref || a_ref == a_player || a_ref->IsDisabled() || a_ref->IsDeleted() || a_ref->As<RE::Actor>()) return;
			if (!IsAnchorBase(a_ref->GetBaseObject())) return;
			if (IsTrackedFast(a_ref->GetFormID())) return;
			if (a_exterior && !ExteriorCellQualifies(a_ref->GetParentCell())) return;
			const auto ppos = a_player->GetPosition();
			const auto apos = a_ref->GetPosition();
			const float dist = ppos.GetDistance(apos);
			if (dist < cfg.minSpawnDistance || dist > cfg.maxSpawnDistance) return;
			// cell cooldown is per anchor cell (exterior anchors may sit in a neighbouring cell)
			if (auto cell = a_ref->GetParentCell()) {
				if (auto it = cellCooldown.find(cell->GetFormID()); it != cellCooldown.end() && GameHours() - it->second < cfg.cellCooldownHours) return;
			}
			Anchor a;
			a.ref = a_ref;
			if (cfg.avoidPlayerView) {
				// Skyrim heading: angle.z = 0 faces +Y, increases clockwise -> forward = (sin z, cos z)
				const float z = a_player->GetAngleZ();
				const float fx = std::sin(z), fy = std::cos(z);
				const float dx = apos.x - ppos.x, dy = apos.y - ppos.y;
				const float len = std::sqrt(dx * dx + dy * dy);
				if (len > 1.0f) {
					const float cosAngle = (fx * dx + fy * dy) / len;
					a.inView = cosAngle > std::cos(cfg.viewConeDegrees * std::numbers::pi_v<float> / 180.0f);
				}
			}
			a_out.push_back(a);
		}

		const SpawnGroup* PickGroup(bool a_interior, int a_level)
		{
			float total = 0.0f;
			for (auto& g : data.groups) {
				if (g.minLevel <= a_level && (a_interior ? g.interior : g.exterior)) total += g.weight;
			}
			if (total <= 0.0f) return nullptr;
			float r = RandFloat(0.0f, total);
			for (auto& g : data.groups) {
				if (!(g.minLevel <= a_level && (a_interior ? g.interior : g.exterior))) continue;
				r -= g.weight;
				if (r <= 0.0f) return &g;
			}
			return nullptr;
		}

		int AliveCount()
		{
			int n = 0;
			for (auto& t : tracked) {
				if (t.actor && t.deathHours < 0.0f) ++n;
			}
			return n;
		}

		void Evaluate()
		{
			auto player = RE::PlayerCharacter::GetSingleton();
			auto pcell = player ? player->GetParentCell() : nullptr;
			if (!player || !pcell || !pcell->IsAttached() || !player->Is3DLoaded()) {
				SFDBG("spawner: player not ready, evaluation dropped");
				return;
			}
			if (IsSiteCell(pcell)) {
				SFDBG("spawner: player is in the Starfall site (hand-placed encounters), no spawn");
				return;
			}
			if (cfg.noSpawnInCombat && player->IsInCombat()) {
				SFDBG("spawner: player in combat, no spawn");
				return;
			}
			const float now = GameHours();
			if (now - lastGlobalSpawn < cfg.globalCooldownHours) {
				SFDBG("spawner: global cooldown ({:.1f}h left)", cfg.globalCooldownHours - (now - lastGlobalSpawn));
				return;
			}
			const int alive = AliveCount();
			if (alive >= cfg.maxAliveSpawns) {
				SFDBG("spawner: cap reached ({} alive)", alive);
				return;
			}

			const bool interior = pcell->IsInteriorCell();
			const RE::FormID rollKey = pcell->GetFormID();
			if (auto it = rolled.find(rollKey); it != rolled.end() && now - it->second < cfg.rerollCooldownHours) {
				SFDBG("spawner: cell {:08X} already rolled recently", rollKey);
				return;
			}

			std::vector<Anchor> anchors;
			if (interior) {
				if (!pending.contains(pcell->GetFormID())) {
					SFDBG("spawner: player cell {:08X} was not part of this load batch", pcell->GetFormID());
					return;
				}
				if (!InteriorQualifies(pcell)) return;
				if (auto it = cellCooldown.find(pcell->GetFormID()); it != cellCooldown.end() && now - it->second < cfg.cellCooldownHours) {
					SFDBG("spawner: interior {:08X} on cooldown", pcell->GetFormID());
					return;
				}
				pcell->ForEachReference([&](RE::TESObjectREFR* a_ref) {
					ConsiderAnchor(a_ref, player, anchors, false);
					return RE::BSContainer::ForEachResult::kContinue;
				});
			} else {
				// wilderness only: neither the player's location nor the cell's may be settled
				if (IsSettled(player->GetCurrentLocation()) || IsSettled(pcell->GetLocation())) {
					SFDBG("spawner: exterior near a settlement, no spawn");
					return;
				}
				if (auto tes = RE::TES::GetSingleton()) {
					tes->ForEachReferenceInRange(player, cfg.maxSpawnDistance, [&](RE::TESObjectREFR* a_ref) {
						ConsiderAnchor(a_ref, player, anchors, true);
						return RE::BSContainer::ForEachResult::kContinue;
					});
				}
			}

			if (anchors.empty()) {
				SFDBG("spawner: no anchor between {} and {} units, no spawn", cfg.minSpawnDistance, cfg.maxSpawnDistance);
				return;
			}

			rolled[rollKey] = now;
			const float chance = interior ? cfg.interiorChance : cfg.exteriorChance;
			const float roll = RandFloat(0.0f, 100.0f);
			if (roll >= chance) {
				SFDBG("spawner: roll {:.1f} >= {:.1f}% ({}), no spawn", roll, chance, interior ? "interior" : "exterior");
				return;
			}

			auto group = PickGroup(interior, player->GetLevel());
			if (!group) {
				SFDBG("spawner: no group fits level {} ({})", player->GetLevel(), interior ? "interior" : "exterior");
				return;
			}

			// prefer anchors the player is not looking at; fall back to any
			std::vector<Anchor*> pool;
			for (auto& a : anchors) {
				if (!a.inView) pool.push_back(&a);
			}
			if (pool.empty()) {
				for (auto& a : anchors) pool.push_back(&a);
			}
			auto anchor = pool[static_cast<std::size_t>(RandInt(0, static_cast<int>(pool.size()) - 1))]->ref;
			auto acell = anchor->GetParentCell();
			const RE::FormID cellID = acell ? acell->GetFormID() : pcell->GetFormID();

			int count = RandInt(group->min, group->max);
			count = std::min(count, cfg.maxAliveSpawns - alive);
			int placed = 0;
			for (int i = 0; i < count; ++i) {
				auto ref = anchor->PlaceObjectAtMe(group->list, false);
				if (!ref) continue;
				Tracked t;
				t.id = ref->GetFormID();
				t.cell = cellID;
				t.actor = ref->As<RE::Actor>() != nullptr;
				t.spawnHours = now;
				AddTracked(t);
				++placed;
			}
			if (!interior && data.canister && RandFloat(0.0f, 100.0f) < cfg.canisterChance) {
				if (auto can = anchor->PlaceObjectAtMe(data.canister, false)) {
					Tracked t;
					t.id = can->GetFormID();
					t.cell = cellID;
					t.actor = false;
					t.spawnHours = now;
					AddTracked(t);
					SFDBG("spawner: canister {:08X} placed", t.id);
				}
			}
			if (placed > 0) {
				cellCooldown[cellID] = now;
				lastGlobalSpawn = now;
			}
			SKSE::log::info("spawner: '{}' x{} at {:08X} (cell {:08X}, {:.0f} units from player)", group->name, placed, anchor->GetFormID(), cellID,
				anchor->GetPosition().GetDistance(player->GetPosition()));
		}
	}

	bool IsTrackedFast(RE::FormID a_ref)
	{
		std::scoped_lock l{ idsLock };
		return trackedIds.contains(a_ref);
	}

	void OnCellLoaded(RE::FormID a_cell)
	{
		if (!cfg.enableSpawner || data.groups.empty()) return;
		pending.insert(a_cell);
		if (evalAt.load() == 0.0) evalAt = RealNow() + cfg.evaluateDelay;
	}

	void OnPlayerCellChanged(RE::FormID a_cell)
	{
		OnCellLoaded(a_cell);
	}

	void Tick()
	{
		const double at = evalAt.load();
		if (at == 0.0 || RealNow() < at) return;
		evalAt = 0.0;
		Housekeep();  // also enforces the dead-for-a-day rule on every cell load batch
		Evaluate();
		pending.clear();
	}

	void OnRefDetached(RE::FormID a_ref)
	{
		auto ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(a_ref);
		if (ref) {
			// detach can be reported while the ref just changes cells; only clean up if it really left
			auto cell = ref->GetParentCell();
			if (cell && cell->IsAttached() && ref->Is3DLoaded()) return;
			RemoveRef(ref, "cell detached");
		}
		EraseTracked(a_ref);
	}

	void OnDeath(RE::FormID a_ref)
	{
		for (auto& t : tracked) {
			if (t.id == a_ref && t.deathHours < 0.0f) {
				t.deathHours = GameHours();
				SFDBG("spawner: tracked {:08X} died", a_ref);
			}
		}
	}

	void Housekeep()
	{
		const float now = GameHours();
		std::vector<RE::FormID> drop;
		for (auto& t : tracked) {
			auto ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(t.id);
			if (!ref || ref->IsDeleted()) {
				drop.push_back(t.id);
				continue;
			}
			if (auto actor = ref->As<RE::Actor>(); actor && actor->IsDead() && t.deathHours < 0.0f) {
				t.deathHours = now;  // died while we weren't looking (e.g. before a save/load)
			}
			const bool expired = t.actor ? (t.deathHours >= 0.0f && now - t.deathHours > cfg.corpseLifetimeHours) : (now - t.spawnHours > cfg.corpseLifetimeHours);
			auto cell = ref->GetParentCell();
			const bool unloaded = !cell || !cell->IsAttached();
			if (expired || unloaded || ref->IsDisabled()) {
				RemoveRef(ref, expired ? "expired" : (unloaded ? "stale, not loaded" : "disabled"));
				drop.push_back(t.id);
			}
		}
		for (auto id : drop) EraseTracked(id);

		// forget old cooldowns so the save record stays small
		std::erase_if(cellCooldown, [&](const auto& kv) { return now - kv.second > cfg.cellCooldownHours; });
		std::erase_if(rolled, [&](const auto& kv) { return now - kv.second > cfg.rerollCooldownHours; });
	}

	void Reset()
	{
		tracked.clear();
		{
			std::scoped_lock l{ idsLock };
			trackedIds.clear();
		}
		cellCooldown.clear();
		lastGlobalSpawn = -1000.0f;
		pending.clear();
		rolled.clear();
		evalAt = 0.0;
	}

	void RebuildIndex()
	{
		std::scoped_lock l{ idsLock };
		trackedIds.clear();
		for (auto& t : tracked) trackedIds.insert(t.id);
	}

	// ---------------- event sinks ----------------
	namespace
	{
		class CellLoadedSink : public RE::BSTEventSink<RE::TESCellFullyLoadedEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESCellFullyLoadedEvent* a_event, RE::BSTEventSource<RE::TESCellFullyLoadedEvent>*) override
			{
				if (a_event && a_event->cell && gameReady) {
					const auto id = a_event->cell->GetFormID();
					SKSE::GetTaskInterface()->AddTask([id]() { OnCellLoaded(id); });
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		class AttachDetachSink : public RE::BSTEventSink<RE::TESCellAttachDetachEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESCellAttachDetachEvent* a_event, RE::BSTEventSource<RE::TESCellAttachDetachEvent>*) override
			{
				// sent for every reference; keep this path cheap (one locked set lookup)
				if (a_event && !a_event->attached && a_event->reference && gameReady) {
					const auto id = a_event->reference->GetFormID();
					if (IsTrackedFast(id)) {
						SKSE::GetTaskInterface()->AddTask([id]() { OnRefDetached(id); });
					}
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		class DeathSink : public RE::BSTEventSink<RE::TESDeathEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESDeathEvent* a_event, RE::BSTEventSource<RE::TESDeathEvent>*) override
			{
				if (a_event && a_event->actorDying && a_event->dead) {
					const auto id = a_event->actorDying->GetFormID();
					if (IsTrackedFast(id)) {
						SKSE::GetTaskInterface()->AddTask([id]() { OnDeath(id); });
					}
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		static CellLoadedSink   loaded;
		static AttachDetachSink detach;
		static DeathSink        death;
		auto holder = RE::ScriptEventSourceHolder::GetSingleton();
		if (!holder) return;
		holder->AddEventSink<RE::TESCellFullyLoadedEvent>(&loaded);
		holder->AddEventSink<RE::TESCellAttachDetachEvent>(&detach);
		holder->AddEventSink<RE::TESDeathEvent>(&death);
	}
}
