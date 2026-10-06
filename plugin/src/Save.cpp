#include "Starfall.h"

// SKSE cosave, plugin id 'SFST'. Records (all version 1):
//   'TRAK' tracked spawns:   u32 count, then per entry FormID ref, FormID cell, u8 isActor, f32 spawnHours, f32 deathHours
//   'CCLD' cell cooldowns:   u32 count, then per entry FormID cell, f32 gameHours
//   'GCLD' global cooldown:  f32 gameHours of the last spawn
//   'INFO' fired infos:      u32 count, then FormID per INFO whose "once" actions already ran
// FormIDs go through ResolveFormID so load order changes are handled; entries that no longer
// resolve are dropped. After loading, Spawner::Housekeep() (posted at kPostLoadGame) removes
// spawns whose cell is not loaded any more or that have been dead too long.

namespace SF::Save
{
	namespace
	{
		constexpr std::uint32_t kID = 'SFST';
		constexpr std::uint32_t kTracked = 'TRAK';
		constexpr std::uint32_t kCellCooldown = 'CCLD';
		constexpr std::uint32_t kGlobalCooldown = 'GCLD';
		constexpr std::uint32_t kInfos = 'INFO';
		constexpr std::uint32_t kVersion = 1;

		template <class T>
		bool W(SKSE::SerializationInterface* a_intfc, const T& a_v)
		{
			return a_intfc->WriteRecordData(&a_v, sizeof a_v);
		}

		template <class T>
		bool R(SKSE::SerializationInterface* a_intfc, T& a_v)
		{
			return a_intfc->ReadRecordData(&a_v, sizeof a_v) == sizeof a_v;
		}

		void OnSave(SKSE::SerializationInterface* a_intfc)
		{
			if (a_intfc->OpenRecord(kTracked, kVersion)) {
				W(a_intfc, static_cast<std::uint32_t>(Spawner::tracked.size()));
				for (auto& t : Spawner::tracked) {
					W(a_intfc, t.id);
					W(a_intfc, t.cell);
					W(a_intfc, static_cast<std::uint8_t>(t.actor ? 1 : 0));
					W(a_intfc, t.spawnHours);
					W(a_intfc, t.deathHours);
				}
			}
			if (a_intfc->OpenRecord(kCellCooldown, kVersion)) {
				W(a_intfc, static_cast<std::uint32_t>(Spawner::cellCooldown.size()));
				for (auto& [cell, hours] : Spawner::cellCooldown) {
					W(a_intfc, cell);
					W(a_intfc, hours);
				}
			}
			if (a_intfc->OpenRecord(kGlobalCooldown, kVersion)) {
				W(a_intfc, Spawner::lastGlobalSpawn);
			}
			if (a_intfc->OpenRecord(kInfos, kVersion)) {
				W(a_intfc, static_cast<std::uint32_t>(Dialogue::fired.size()));
				for (auto id : Dialogue::fired) W(a_intfc, id);
			}
		}

		void OnLoad(SKSE::SerializationInterface* a_intfc)
		{
			std::uint32_t type, version, length;
			while (a_intfc->GetNextRecordInfo(type, version, length)) {
				if (version != kVersion) {
					SKSE::log::warn("cosave: record {:08X} has unknown version {}, skipped", type, version);
					continue;
				}
				if (type == kTracked) {
					std::uint32_t n = 0;
					if (!R(a_intfc, n)) continue;
					for (std::uint32_t i = 0; i < n; ++i) {
						Spawner::Tracked t;
						std::uint8_t     actor = 1;
						if (!R(a_intfc, t.id) || !R(a_intfc, t.cell) || !R(a_intfc, actor) || !R(a_intfc, t.spawnHours) || !R(a_intfc, t.deathHours)) break;
						t.actor = actor != 0;
						RE::FormID id = 0, cell = 0;
						if (!a_intfc->ResolveFormID(t.id, id)) continue;
						t.id = id;
						t.cell = a_intfc->ResolveFormID(t.cell, cell) ? cell : 0;
						Spawner::tracked.push_back(t);
					}
					Spawner::RebuildIndex();
				} else if (type == kCellCooldown) {
					std::uint32_t n = 0;
					if (!R(a_intfc, n)) continue;
					for (std::uint32_t i = 0; i < n; ++i) {
						RE::FormID cell = 0, resolved = 0;
						float      hours = 0.0f;
						if (!R(a_intfc, cell) || !R(a_intfc, hours)) break;
						if (a_intfc->ResolveFormID(cell, resolved)) Spawner::cellCooldown[resolved] = hours;
					}
				} else if (type == kGlobalCooldown) {
					R(a_intfc, Spawner::lastGlobalSpawn);
				} else if (type == kInfos) {
					std::uint32_t n = 0;
					if (!R(a_intfc, n)) continue;
					for (std::uint32_t i = 0; i < n; ++i) {
						RE::FormID id = 0, resolved = 0;
						if (!R(a_intfc, id)) break;
						if (a_intfc->ResolveFormID(id, resolved)) Dialogue::fired.insert(resolved);
					}
				}
			}
			SKSE::log::info("cosave: {} tracked spawns, {} cell cooldowns, {} fired infos", Spawner::tracked.size(), Spawner::cellCooldown.size(), Dialogue::fired.size());
		}

		void OnRevert(SKSE::SerializationInterface*)
		{
			Spawner::Reset();
			Dialogue::Reset();
		}
	}

	void Register()
	{
		if (auto ser = SKSE::GetSerializationInterface()) {
			ser->SetUniqueID(kID);
			ser->SetSaveCallback(OnSave);
			ser->SetLoadCallback(OnLoad);
			ser->SetRevertCallback(OnRevert);
		}
	}
}
