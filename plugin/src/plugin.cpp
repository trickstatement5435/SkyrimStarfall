// StarfallSite.dll: runtime "script engine" for the Starfall Research Site expansion.
//
// Subsystems (one .cpp each):
//   Spawner.cpp   world spawner for headcrab/zombie groups + crashed canisters, with cleanup
//   Pounce.cpp    experimental headcrab leap attack
//   Site.cpp      site presence (quest stage 10 on first entry) + NPC to NPC chatter
//   Dialogue.cpp  INFO-driven quest/inventory actions
//   Save.cpp      SKSE cosave ('SFST')
//   Forms.cpp     forms.json loader, Config.cpp StarfallSite.ini loader, Json.cpp tiny JSON reader
//
// Data: Data/SKSE/Plugins/StarfallSite/forms.json (schema: DESIGN.md, sample: forms.sample.json).
// Every key is optional; anything that fails to resolve is logged and skipped.
//
// Additive extensions to the DESIGN.md schema (all optional, old files stay valid):
//   - Any {"plugin","id"} id may be a hex string ("0x80A", "80A") or a JSON number.
//   - spawner.groups[].plugin           per-group plugin override (default spawner.plugin)
//   - spawner.canister.id               accepted as an alias of "static"
//   - actors.<EDID>                     may point at a placed actor (ACHR) or a base NPC; for an NPC
//                                       the loaded actor with that base is used
//   - conversations[].plugin            plugin of the topic ids (default StarfallSite.esp)
//   - conversations[].lines[].plugin    per-line override
//   - conversations[].lines[].text      line text, only used to time the line: max(2.5s, chars/14)
//   - conversations[].lines[].seconds   explicit wait after the line, overrides "text"
//   - infoActions[].plugin              plugin of the INFO id (default StarfallSite.esp)
//   - infoActions[].addToFaction        {"plugin","id","rank"} adds the player to a faction
//   - infoActions[].unlock              {"plugin","id"} or a list of them: references to unlock
//   - infoActions[].enable              list of {"plugin","id"} (or one object): references to enable
//   - infoActions[].once                true = run at most once per playthrough (saved in the cosave)
//   - siteWorldspace                    exterior cells of this worldspace also count as site cells
//
// Threading: see Starfall.h. All game work happens on the main thread through SKSE tasks.

#include "Starfall.h"

namespace SF
{
	namespace
	{
		std::mt19937& Rng()
		{
			static std::mt19937 rng{ std::random_device{}() };
			return rng;
		}
	}

	double RealNow()
	{
		using namespace std::chrono;
		return duration<double>(steady_clock::now().time_since_epoch()).count();
	}

	float GameHours()
	{
		auto cal = RE::Calendar::GetSingleton();
		return cal ? cal->GetCurrentGameTime() * 24.0f : 0.0f;  // GetCurrentGameTime() is in days
	}

	float RandFloat(float a_min, float a_max)
	{
		if (a_max <= a_min) return a_min;
		std::uniform_real_distribution<float> d(a_min, a_max);
		return d(Rng());
	}

	int RandInt(int a_min, int a_max)
	{
		if (a_max <= a_min) return a_min;
		std::uniform_int_distribution<int> d(a_min, a_max);
		return d(Rng());
	}

	// ------------------------------------------------------------------
	// Ticker: a sleeping background thread that wakes 4x a second, looks at a few atomics and,
	// only when some subsystem has work (a crab in combat, the player inside the site, a pending
	// spawner evaluation), queues ONE task on the main thread. Nothing runs per frame and nothing
	// is queued while all subsystems are idle.
	// ------------------------------------------------------------------
	namespace Ticker
	{
		namespace
		{
			std::atomic<bool> queued{ false };

			void OnTick()
			{
				queued = false;
				if (!gameReady) return;
				if (auto ui = RE::UI::GetSingleton(); ui && ui->GameIsPaused()) return;  // menus open
				Spawner::Tick();
				if (cfg.enablePounce) Pounce::Tick();
				Site::Tick();
			}
		}

		void Start()
		{
			static std::atomic<bool> started{ false };
			if (started.exchange(true)) return;
			std::thread([]() {
				while (true) {
					std::this_thread::sleep_for(250ms);
					if (!gameReady) continue;
					const double at = Spawner::evalAt.load();
					const bool   want = Pounce::activeCount.load() > 0 || Site::active.load() || (at > 0.0 && RealNow() >= at);
					if (want && !queued.exchange(true)) {
						if (auto tasks = SKSE::GetTaskInterface()) {
							tasks->AddTask([]() { OnTick(); });
						} else {
							queued = false;
						}
					}
				}
			}).detach();
		}
	}

	namespace
	{
		void AfterLoad()
		{
			gameReady = true;
			Site::Register();  // PlayerCharacter exists by now; no-op if already registered
			SKSE::GetTaskInterface()->AddTask([]() {
				Gate::Place(true);     // move the checkpoint gate next to its anchor; snaps now if the land is loaded, else when its cell attaches
				Gate::UpdateLock();
				Spawner::Housekeep();  // drop stale spawns restored from the cosave
				Site::OnPlayerCellChanged();
				if (auto player = RE::PlayerCharacter::GetSingleton(); player && player->GetParentCell()) {
					Spawner::OnPlayerCellChanged(player->GetParentCell()->GetFormID());
				}
			});
		}
	}
}

static void SetupLog()
{
	auto dir = SKSE::log::log_directory();
	if (!dir) {
		return;
	}
	auto path = *dir / "StarfallSite.log";
	auto sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(path.string(), true);
	auto log = std::make_shared<spdlog::logger>("global", std::move(sink));
	log->set_level(spdlog::level::info);
	log->flush_on(spdlog::level::info);
	spdlog::set_default_logger(std::move(log));
}

SKSEPluginLoad(const SKSE::LoadInterface* skse)
{
	SKSE::Init(skse);
	SetupLog();
	SKSE::log::info("StarfallSite loading");
	if (REL::Module::IsVR()) {
		SKSE::log::error("Skyrim VR is not supported");
		return false;
	}

	SF::LoadConfig();
	SF::Save::Register();

	SKSE::GetMessagingInterface()->RegisterListener([](SKSE::MessagingInterface::Message* msg) {
		switch (msg->type) {
		case SKSE::MessagingInterface::kDataLoaded:
			SF::LoadForms();
			SF::Spawner::Register();
			SF::Pounce::Register();
			SF::Dialogue::Register();
			SF::Site::Register();
			SF::Gate::Register();
			SF::Ticker::Start();
			SKSE::log::info("Event handlers registered");
			break;
		case SKSE::MessagingInterface::kPreLoadGame:
			SF::gameReady = false;
			SF::Pounce::Reset();
			SF::Site::Reset();
			break;
		case SKSE::MessagingInterface::kNewGame:
			SF::Pounce::Reset();
			SF::Site::Reset();
			SF::Spawner::Reset();
			SF::Dialogue::Reset();
			SF::AfterLoad();
			break;
		case SKSE::MessagingInterface::kPostLoadGame:
			SF::AfterLoad();
			break;
		default:
			break;
		}
	});

	return true;
}
