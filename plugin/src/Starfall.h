#pragma once

// Shared declarations for StarfallSite.dll.
// Threading rule for the whole plugin: game state is only read or written on the main
// (game) thread. Event sinks that may be called elsewhere copy what they need and hand the
// work to SKSE::GetTaskInterface()->AddTask(). The background ticker thread only reads
// atomics and queues tasks; it never touches a game object.

#define SFDBG(...)                              \
	do {                                        \
		if (::SF::cfg.debugLog) {               \
			SKSE::log::info(__VA_ARGS__);       \
		}                                       \
	} while (false)

namespace SF
{
	// ------------------------------------------------------------------
	// Config (Data/SKSE/Plugins/StarfallSite.ini)
	// ------------------------------------------------------------------
	struct Config
	{
		bool debugLog = false;

		// world spawner
		bool  enableSpawner = true;
		float cellCooldownHours = 72.0f;    // in-game hours before the same cell can spawn again
		float globalCooldownHours = 2.0f;   // in-game hours between any two spawns
		float interiorChance = 18.0f;       // percent per qualifying interior arrival
		float exteriorChance = 7.0f;        // percent per qualifying exterior evaluation
		int   maxAliveSpawns = 10;          // cap on living spawned actors
		bool  noSpawnInCombat = true;
		float minSpawnDistance = 1500.0f;
		float maxSpawnDistance = 4500.0f;
		bool  avoidPlayerView = true;       // prefer anchors outside the player's facing cone
		float viewConeDegrees = 35.0f;      // half angle of that cone
		float canisterChance = 25.0f;       // percent of exterior spawns that also drop a canister
		float corpseLifetimeHours = 24.0f;  // dead spawns (and canisters) are removed after this
		float rerollCooldownHours = 6.0f;   // a cell that rolled and failed is not rolled again for this long
		float evaluateDelay = 2.0f;         // real seconds after a cell load before evaluating (lets the player settle)

		// headcrab pounce
		bool        enablePounce = true;
		float       pounceMinRange = 120.0f;
		float       pounceMaxRange = 480.0f;
		float       pounceCooldown = 3.0f;  // real seconds per crab
		float       pounceSpeed = 700.0f;   // game units per second, horizontal
		float       pounceUp = 260.0f;      // game units per second, vertical
		std::string pounceAnimEvent = "attackStart";

		// NPC to NPC chatter
		bool  enableChatter = true;
		float chatterInterval = 45.0f;        // real seconds, randomized +-50%
		float conversationCooldown = 600.0f;  // real seconds before the same conversation can repeat
		float chatterPairDistance = 450.0f;
		float chatterPlayerDistance = 2000.0f;

		// dialogue actions
		bool actionOnTopicStart = false;  // 0 = apply when the INFO finishes, 1 = when it starts

		// checkpoint gate in Skyrim. Absolute placement (from console getpos) wins when GateX/GateY are not 0;
		// otherwise the gate sits at the Embershard Mine map marker + GateOffsetX/Y.
		float gateX = 0.0f, gateY = 0.0f, gateZ = 0.0f;  // GateZ 0 = snap to the ground
		float gateAngle = 0.0f;                          // degrees, direction the gate door faces (0 = north)
		float gateOffsetX = std::numeric_limits<float>::quiet_NaN();
		float gateOffsetY = std::numeric_limits<float>::quiet_NaN();
		bool  requireDevice = true;                      // gate stays locked without the Gravity Gun
	};
	inline Config cfg;
	void LoadConfig();

	// ------------------------------------------------------------------
	// Data from forms.json (resolved once at kDataLoaded, read-only afterwards)
	// ------------------------------------------------------------------
	struct SpawnGroup
	{
		std::string          name;
		RE::TESBoundObject*  list = nullptr;  // leveled NPC list (any bound object is accepted)
		int                  min = 1;
		int                  max = 1;
		float                weight = 1.0f;
		int                  minLevel = 1;
		bool                 interior = true;
		bool                 exterior = true;
	};

	struct ChatLine
	{
		bool          speakerIsA = true;
		RE::TESTopic* topic = nullptr;
		float         seconds = 4.0f;  // estimated playback time before the next line
	};

	struct Conversation
	{
		std::string           a;
		std::string           b;
		std::vector<ChatLine> lines;
		int                   minStage = 0;
		int                   maxStage = 1000;
		float                 weight = 1.0f;
	};

	struct ItemAction
	{
		RE::TESBoundObject* item = nullptr;
		std::int32_t        count = 1;
	};

	struct InfoAction
	{
		RE::FormID                info = 0;
		std::optional<int>        setStage;
		std::vector<int>          objectivesDisplayed;
		std::vector<int>          objectivesCompleted;
		std::optional<ItemAction> removeItem;
		std::optional<ItemAction> addItem;
		RE::TESFaction*           faction = nullptr;
		std::int8_t               factionRank = 0;
		std::vector<RE::FormID>   unlock;  // references
		std::vector<RE::FormID>   enable;  // references
		bool                      once = false;
		bool                      openVendor = false;  // opens the vendor actor's barter menu
	};

	struct GateRef
	{
		RE::FormID id = 0;
		float      dx = 0.0f, dy = 0.0f, dz = 0.0f, angle = 0.0f;  // offset from the gate door (door space), degrees
		bool       door = false;
	};

	struct Data
	{
		std::vector<SpawnGroup>                        groups;
		RE::TESBoundObject*                            canister = nullptr;
		RE::BGSKeyword*                                headcrabKeyword = nullptr;
		RE::BGSKeyword*                                zombieKeyword = nullptr;
		RE::TESWorldSpace*                             siteWorldspace = nullptr;
		std::unordered_set<RE::FormID>                 siteCells;
		std::unordered_map<std::string, RE::TESForm*>  actors;  // EDID -> placed ref (ACHR) or base NPC
		std::vector<Conversation>                      conversations;
		std::unordered_map<RE::FormID, InfoAction>     infoActions;  // keyed by the INFO's runtime FormID
		RE::TESQuest*                                  quest = nullptr;
		RE::FormID                                     vendorActor = 0;
		// gate
		std::vector<GateRef>                           gateRefs;
		RE::FormID                                     gateAnchor = 0;
		float                                          gateOffX = 900.0f, gateOffY = -600.0f, gateFacing = 0.0f;
		RE::FormID                                     gateDoor = 0, arrivalDoor = 0;
		RE::TESBoundObject*                            gateItem = nullptr;
		std::string                                    gateDenied;
		bool                                           loaded = false;
	};
	inline Data data;
	void LoadForms();

	// ------------------------------------------------------------------
	// Shared helpers
	// ------------------------------------------------------------------
	double RealNow();    // seconds, steady clock
	float  GameHours();  // in-game hours since the start of the game
	float  RandFloat(float a_min, float a_max);
	int    RandInt(int a_min, int a_max);
	bool   IsSiteCell(const RE::TESObjectCELL* a_cell);

	// true between kPostLoadGame/kNewGame and the next kPreLoadGame
	inline std::atomic<bool> gameReady{ false };

	// ------------------------------------------------------------------
	// Papyrus VM dispatch (no scripts needed in the ESP)
	// ------------------------------------------------------------------
	namespace Papyrus
	{
		// Calls a_class.a_fn on the script object bound to a_ptr (binding a plain one if needed).
		// Takes ownership of a_args. Must run on the main thread.
		void CallOn(RE::VMTypeID a_type, const void* a_ptr, const char* a_class, const char* a_fn, RE::BSScript::IFunctionArguments* a_args);

		void CallActor(RE::Actor* a_actor, const char* a_fn, RE::BSScript::IFunctionArguments* a_args);
		void CallRef(RE::TESObjectREFR* a_ref, const char* a_fn, RE::BSScript::IFunctionArguments* a_args);
		void CallQuest(RE::TESQuest* a_quest, const char* a_fn, RE::BSScript::IFunctionArguments* a_args);
		void Notify(const std::string& a_text);  // Debug.Notification
	}

	// ------------------------------------------------------------------
	// Subsystems
	// ------------------------------------------------------------------
	namespace Spawner
	{
		struct Tracked
		{
			RE::FormID id = 0;       // spawned reference
			RE::FormID cell = 0;     // cell it was spawned for (cooldown bookkeeping)
			bool       actor = true;  // false for the canister static
			float      spawnHours = 0.0f;
			float      deathHours = -1.0f;  // < 0 while alive
		};

		void Register();  // event sinks
		void OnCellLoaded(RE::FormID a_cell);
		void OnPlayerCellChanged(RE::FormID a_cell);
		void OnRefDetached(RE::FormID a_ref);
		void OnDeath(RE::FormID a_ref);
		void Tick();       // runs the delayed evaluation when due
		void Housekeep();  // cleanup pass (dead too long, unloaded, missing)
		void Reset();      // new game / before load

		bool IsTrackedFast(RE::FormID a_ref);  // thread safe
		void RebuildIndex();                   // after the cosave filled `tracked`

		// saved state
		inline std::vector<Tracked>                     tracked;
		inline std::unordered_map<RE::FormID, float>   cellCooldown;  // cell -> game hours of last spawn
		inline float                                    lastGlobalSpawn = -1000.0f;

		inline std::atomic<double> evalAt{ 0.0 };  // real time of the pending evaluation, 0 = none
	}

	namespace Pounce
	{
		void Register();
		void OnCombat(RE::FormID a_actor, bool a_inCombat);
		void Tick();
		void Reset();
		inline std::atomic<int> activeCount{ 0 };
	}

	namespace Site
	{
		void Register();
		void OnPlayerCellChanged();
		void Tick();
		void Reset();
		inline std::atomic<bool> active{ false };
	}

	namespace Dialogue
	{
		void Register();
		void OnInfo(RE::FormID a_info);
		void Reset();
		inline std::unordered_set<RE::FormID> fired;  // saved: INFOs whose "once" actions already ran
	}

	namespace Ticker
	{
		void Start();
	}

	namespace Gate
	{
		void Register();
		void Place(bool a_snap);  // move the gate group next to its anchor (snap to the ground when the land is loaded)
		void UpdateLock();        // lock/unlock the gate door for the required item
		bool IsGateRef(RE::FormID a_id);
	}

	namespace Save
	{
		void Register();
	}
}
