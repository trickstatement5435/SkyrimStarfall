#include "Starfall.h"

// Same hand parser style as GravityGun.ini: "key = value", ';' or '#' comments,
// [Sections] are only for readability (keys are unique across sections), keys are case-insensitive.

namespace SF
{
	namespace
	{
		std::string Trim(std::string s)
		{
			const auto ws = " \t\r\n";
			s.erase(0, s.find_first_not_of(ws));
			const auto end = s.find_last_not_of(ws);
			s.erase(end == std::string::npos ? 0 : end + 1);
			return s;
		}
	}

	void LoadConfig()
	{
		std::ifstream file("Data/SKSE/Plugins/StarfallSite.ini");
		if (!file) {
			SKSE::log::info("No StarfallSite.ini found, using defaults");
			return;
		}

		std::string line;
		while (std::getline(file, line)) {
			line = Trim(line);
			if (line.empty() || line[0] == ';' || line[0] == '#' || line[0] == '[') {
				continue;
			}
			const auto eq = line.find('=');
			if (eq == std::string::npos) {
				continue;
			}
			auto key = Trim(line.substr(0, eq));
			auto val = Trim(line.substr(eq + 1));
			if (const auto c = val.find(';'); c != std::string::npos) {
				val = Trim(val.substr(0, c));
			}
			std::transform(key.begin(), key.end(), key.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });

			auto f = [&](float& out) { out = std::stof(val); };
			auto b = [&](bool& out) { out = std::stoi(val) != 0; };
			auto i = [&](int& out) { out = std::stoi(val); };

			try {
				if (key == "debuglog") b(cfg.debugLog);

				else if (key == "enablespawner") b(cfg.enableSpawner);
				else if (key == "cellcooldownhours") f(cfg.cellCooldownHours);
				else if (key == "globalcooldownhours") f(cfg.globalCooldownHours);
				else if (key == "interiorchance") f(cfg.interiorChance);
				else if (key == "exteriorchance") f(cfg.exteriorChance);
				else if (key == "maxalivespawns") i(cfg.maxAliveSpawns);
				else if (key == "nospawnincombat") b(cfg.noSpawnInCombat);
				else if (key == "minspawndistance") f(cfg.minSpawnDistance);
				else if (key == "maxspawndistance") f(cfg.maxSpawnDistance);
				else if (key == "avoidplayerview") b(cfg.avoidPlayerView);
				else if (key == "viewconedegrees") f(cfg.viewConeDegrees);
				else if (key == "canisterchance") f(cfg.canisterChance);
				else if (key == "corpselifetimehours") f(cfg.corpseLifetimeHours);
				else if (key == "rerollcooldownhours") f(cfg.rerollCooldownHours);
				else if (key == "evaluatedelay") f(cfg.evaluateDelay);

				else if (key == "enablepounce") b(cfg.enablePounce);
				else if (key == "pounceminrange") f(cfg.pounceMinRange);
				else if (key == "pouncemaxrange") f(cfg.pounceMaxRange);
				else if (key == "pouncecooldown") f(cfg.pounceCooldown);
				else if (key == "pouncespeed") f(cfg.pounceSpeed);
				else if (key == "pounceup") f(cfg.pounceUp);
				else if (key == "pounceanimevent") cfg.pounceAnimEvent = val;

				else if (key == "enablechatter") b(cfg.enableChatter);
				else if (key == "chatterinterval") f(cfg.chatterInterval);
				else if (key == "conversationcooldown") f(cfg.conversationCooldown);
				else if (key == "chatterpairdistance") f(cfg.chatterPairDistance);
				else if (key == "chatterplayerdistance") f(cfg.chatterPlayerDistance);

				else if (key == "actionontopicstart") b(cfg.actionOnTopicStart);

				else if (key == "gatex") f(cfg.gateX);
				else if (key == "gatey") f(cfg.gateY);
				else if (key == "gatez") f(cfg.gateZ);
				else if (key == "gateangle") f(cfg.gateAngle);
				else if (key == "gateoffsetx") f(cfg.gateOffsetX);
				else if (key == "gateoffsety") f(cfg.gateOffsetY);
				else if (key == "requiredevice") b(cfg.requireDevice);
				else SKSE::log::warn("StarfallSite.ini: unknown key '{}'", key);
			} catch (...) {
				SKSE::log::warn("StarfallSite.ini: bad value for {}: '{}'", key, val);
			}
		}

		// keep the numbers sane
		cfg.minSpawnDistance = std::max(0.0f, cfg.minSpawnDistance);
		cfg.maxSpawnDistance = std::max(cfg.minSpawnDistance + 1.0f, cfg.maxSpawnDistance);
		cfg.pounceMaxRange = std::max(cfg.pounceMinRange, cfg.pounceMaxRange);
		cfg.chatterInterval = std::max(5.0f, cfg.chatterInterval);
		cfg.evaluateDelay = std::clamp(cfg.evaluateDelay, 0.25f, 30.0f);
		cfg.maxAliveSpawns = std::max(0, cfg.maxAliveSpawns);

		SKSE::log::info("Config: spawner={} pounce={} chatter={} debug={}", cfg.enableSpawner, cfg.enablePounce, cfg.enableChatter, cfg.debugLog);
	}
}
