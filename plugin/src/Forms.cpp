#include "Json.h"
#include "Starfall.h"

// Reads Data/SKSE/Plugins/StarfallSite/forms.json (written by the ESP generator).
// Every key is optional. Anything that fails to parse or resolve is logged and skipped;
// the subsystem that needed it just stays inactive.

namespace SF
{
	namespace
	{
		constexpr std::string_view kDefaultPlugin = "StarfallSite.esp"sv;

		std::optional<RE::FormID> ParseID(const Json::Value* a_v)
		{
			if (!a_v) return std::nullopt;
			if (a_v->IsNumber()) {
				if (a_v->n < 0) return std::nullopt;
				return static_cast<RE::FormID>(a_v->n);
			}
			if (!a_v->IsString()) return std::nullopt;
			std::string_view s = a_v->s;
			while (!s.empty() && s.front() == ' ') s.remove_prefix(1);
			if (s.size() >= 2 && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s.remove_prefix(2);
			if (s.empty()) return std::nullopt;
			RE::FormID id = 0;
			const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), id, 16);
			if (ec != std::errc{} || ptr != s.data() + s.size()) return std::nullopt;
			return id;
		}

		// a_v is either {"plugin": "...", "id": "0x..."} or a bare id (uses a_defPlugin).
		// a_idKey lets "canister" use "static" as its id key.
		RE::TESForm* Resolve(const Json::Value* a_v, std::string_view a_defPlugin, std::string_view a_what, std::string_view a_idKey = "id"sv)
		{
			if (!a_v || a_v->IsNull()) return nullptr;
			std::string             plugin(a_defPlugin);
			std::optional<RE::FormID> id;
			if (a_v->IsObject()) {
				plugin = a_v->Str("plugin", a_defPlugin);
				id = ParseID(a_v->Get(a_idKey));
				if (!id && a_idKey != "id"sv) id = ParseID(a_v->Get("id"));
			} else {
				id = ParseID(a_v);
			}
			if (!id) {
				SKSE::log::warn("forms.json: {} has no usable id, skipped", a_what);
				return nullptr;
			}
			auto dh = RE::TESDataHandler::GetSingleton();
			auto form = dh ? dh->LookupForm(*id & 0x00FFFFFF, plugin) : nullptr;
			if (!form) {
				SKSE::log::warn("forms.json: {} {:X} in {} not found (plugin missing or id wrong), skipped", a_what, *id, plugin);
				return nullptr;
			}
			return form;
		}

		template <class T>
		T* ResolveAs(const Json::Value* a_v, std::string_view a_defPlugin, std::string_view a_what, std::string_view a_idKey = "id"sv)
		{
			auto form = Resolve(a_v, a_defPlugin, a_what, a_idKey);
			if (!form) return nullptr;
			auto t = form->As<T>();
			if (!t) {
				SKSE::log::warn("forms.json: {} {:08X} has the wrong form type ({}), skipped", a_what, form->GetFormID(), static_cast<int>(form->GetFormType()));
			}
			return t;
		}

		// accepts a single object or an array of objects
		std::vector<RE::FormID> ResolveRefList(const Json::Value* a_v, std::string_view a_what)
		{
			std::vector<RE::FormID> out;
			if (!a_v) return out;
			auto one = [&](const Json::Value* v) {
				if (auto ref = ResolveAs<RE::TESObjectREFR>(v, kDefaultPlugin, a_what)) out.push_back(ref->GetFormID());
			};
			if (a_v->IsArray()) {
				for (auto& v : a_v->items) one(&v);
			} else {
				one(a_v);
			}
			return out;
		}

		std::vector<int> IntList(const Json::Value* a_v)
		{
			std::vector<int> out;
			if (!a_v) return out;
			if (a_v->IsNumber()) {
				out.push_back(static_cast<int>(a_v->n));
			} else if (a_v->IsArray()) {
				for (auto& v : a_v->items) {
					if (v.IsNumber()) out.push_back(static_cast<int>(v.n));
				}
			}
			return out;
		}

		std::optional<ItemAction> Item(const Json::Value* a_v, std::string_view a_what)
		{
			if (!a_v || !a_v->IsObject()) return std::nullopt;
			auto obj = ResolveAs<RE::TESBoundObject>(a_v, kDefaultPlugin, a_what);
			if (!obj) return std::nullopt;
			ItemAction a;
			a.item = obj;
			a.count = std::max(1, static_cast<int>(a_v->Num("count", 1)));
			return a;
		}

		void LoadSpawner(const Json::Value& a_root)
		{
			auto sp = a_root.Get("spawner");
			if (!sp || !sp->IsObject()) return;
			const auto plugin = sp->Str("plugin", "StarfallCreatures.esp");
			if (auto groups = sp->Get("groups"); groups && groups->IsArray()) {
				for (auto& g : groups->items) {
					if (!g.IsObject()) continue;
					SpawnGroup grp;
					grp.name = g.Str("name", "unnamed");
					const auto gPlugin = g.Str("plugin", plugin);  // extension: per-group plugin override
					grp.list = ResolveAs<RE::TESBoundObject>(g.Get("lvln"), gPlugin, std::format("spawner group '{}'", grp.name));
					if (!grp.list) continue;
					grp.min = std::max(1, static_cast<int>(g.Num("min", 1)));
					grp.max = std::max(grp.min, static_cast<int>(g.Num("max", grp.min)));
					grp.weight = static_cast<float>(g.Num("weight", 1.0));
					grp.minLevel = static_cast<int>(g.Num("minLevel", 1));
					grp.interior = g.Bool("interior", true);
					grp.exterior = g.Bool("exterior", true);
					if (grp.weight <= 0.0f) continue;
					data.groups.push_back(std::move(grp));
				}
			}
			if (auto c = sp->Get("canister")) {
				data.canister = ResolveAs<RE::TESBoundObject>(c, "StarfallSite.esp", "canister", "static");
			}
		}

		void LoadConversations(const Json::Value& a_root)
		{
			auto convs = a_root.Get("conversations");
			if (!convs || !convs->IsArray()) return;
			int index = 0;
			for (auto& c : convs->items) {
				++index;
				if (!c.IsObject()) continue;
				Conversation conv;
				conv.a = c.Str("a", "");
				conv.b = c.Str("b", "");
				conv.minStage = static_cast<int>(c.Num("minStage", 0));
				conv.maxStage = static_cast<int>(c.Num("maxStage", 1000));
				conv.weight = static_cast<float>(c.Num("weight", 1.0));
				const auto cPlugin = c.Str("plugin", kDefaultPlugin);  // extension
				if (!data.actors.contains(conv.a) || !data.actors.contains(conv.b)) {
					SKSE::log::warn("forms.json: conversation {} names actors '{}'/'{}' that are not in \"actors\", skipped", index, conv.a, conv.b);
					continue;
				}
				bool ok = true;
				if (auto lines = c.Get("lines"); lines && lines->IsArray()) {
					for (auto& l : lines->items) {
						if (!l.IsObject()) continue;
						ChatLine line;
						line.speakerIsA = l.Str("who", "a") != "b";
						const auto lPlugin = l.Str("plugin", cPlugin);  // extension
						line.topic = ResolveAs<RE::TESTopic>(l.Get("topic"), lPlugin, std::format("conversation {} topic", index));
						if (!line.topic) {
							ok = false;
							break;
						}
						// estimated playback time: optional explicit "seconds" (extension), else from "text", else 4s
						if (auto secs = l.Get("seconds"); secs && secs->IsNumber()) {
							line.seconds = static_cast<float>(secs->n);
						} else if (auto text = l.Get("text"); text && text->IsString()) {
							line.seconds = std::max(2.5f, static_cast<float>(text->s.size()) / 14.0f);
						} else {
							line.seconds = 4.0f;
						}
						conv.lines.push_back(line);
					}
				}
				if (!ok || conv.lines.empty() || conv.weight <= 0.0f) {
					SKSE::log::warn("forms.json: conversation {} ({} / {}) has unresolved or no lines, skipped", index, conv.a, conv.b);
					continue;
				}
				data.conversations.push_back(std::move(conv));
			}
		}

		void LoadInfoActions(const Json::Value& a_root)
		{
			auto list = a_root.Get("infoActions");
			if (!list || !list->IsArray()) return;
			for (auto& a : list->items) {
				if (!a.IsObject()) continue;
				const auto plugin = a.Str("plugin", kDefaultPlugin);  // extension: plugin of the INFO
				auto info = ResolveAs<RE::TESTopicInfo>(a.Get("info"), plugin, "infoActions info");
				if (!info) continue;
				InfoAction act;
				act.info = info->GetFormID();
				if (auto s = a.Get("setStage"); s && s->IsNumber()) act.setStage = static_cast<int>(s->n);
				act.objectivesDisplayed = IntList(a.Get("objectiveDisplayed"));
				act.objectivesCompleted = IntList(a.Get("objectiveCompleted"));
				act.removeItem = Item(a.Get("removeItem"), "removeItem");
				act.addItem = Item(a.Get("addItem"), "addItem");
				if (auto fac = a.Get("addToFaction"); fac && fac->IsObject()) {
					act.faction = ResolveAs<RE::TESFaction>(fac, kDefaultPlugin, "addToFaction");
					act.factionRank = static_cast<std::int8_t>(std::clamp(static_cast<int>(fac->Num("rank", 0)), -128, 127));
				}
				act.unlock = ResolveRefList(a.Get("unlock"), "unlock");
				act.enable = ResolveRefList(a.Get("enable"), "enable");
				act.once = a.Bool("once", false);
				act.openVendor = a.Bool("openVendor", false);
				data.infoActions[act.info] = std::move(act);
			}
		}
	}

	void LoadForms()
	{
		data = Data{};
		const char* path = "Data/SKSE/Plugins/StarfallSite/forms.json";
		std::ifstream file(path, std::ios::binary);
		if (!file) {
			SKSE::log::warn("{} not found: StarfallSite.dll stays idle", path);
			return;
		}
		std::stringstream ss;
		ss << file.rdbuf();
		std::string err;
		auto root = Json::Parse(ss.str(), err);
		if (!root || !root->IsObject()) {
			SKSE::log::error("forms.json could not be parsed: {}", root ? "top level is not an object"s : err);
			return;
		}

		LoadSpawner(*root);
		data.headcrabKeyword = ResolveAs<RE::BGSKeyword>(root->Get("headcrabKeyword"), "StarfallCreatures.esp", "headcrabKeyword");
		data.zombieKeyword = ResolveAs<RE::BGSKeyword>(root->Get("zombieKeyword"), "StarfallCreatures.esp", "zombieKeyword");
		data.siteWorldspace = ResolveAs<RE::TESWorldSpace>(root->Get("siteWorldspace"), kDefaultPlugin, "siteWorldspace");
		if (auto cells = root->Get("siteCells"); cells && cells->IsArray()) {
			for (auto& c : cells->items) {
				if (auto cell = ResolveAs<RE::TESObjectCELL>(&c, kDefaultPlugin, "siteCells entry")) data.siteCells.insert(cell->GetFormID());
			}
		}
		if (auto actors = root->Get("actors"); actors && actors->IsObject()) {
			for (std::size_t i = 0; i < actors->keys.size(); ++i) {
				auto form = Resolve(&actors->items[i], kDefaultPlugin, std::format("actor '{}'", actors->keys[i]));
				if (!form) continue;
				if (!form->Is(RE::FormType::ActorCharacter) && !form->Is(RE::FormType::NPC)) {
					SKSE::log::warn("forms.json: actor '{}' is neither a placed actor nor an NPC, skipped", actors->keys[i]);
					continue;
				}
				data.actors[actors->keys[i]] = form;
			}
		}
		LoadConversations(*root);
		LoadInfoActions(*root);
		data.quest = ResolveAs<RE::TESQuest>(root->Get("quest"), kDefaultPlugin, "quest");
		if (auto v = root->Get("vendor"); v && v->IsObject()) {
			if (auto ref = ResolveAs<RE::TESObjectREFR>(v->Get("actor"), kDefaultPlugin, "vendor actor")) data.vendorActor = ref->GetFormID();
		}
		if (auto g = root->Get("gate"); g && g->IsObject()) {
			if (auto anchor = ResolveAs<RE::TESObjectREFR>(g->Get("anchor"), "Skyrim.esm", "gate anchor")) data.gateAnchor = anchor->GetFormID();
			if (auto off = g->Get("offset"); off && off->IsArray() && off->items.size() >= 2) {
				data.gateOffX = static_cast<float>(off->items[0].n);
				data.gateOffY = static_cast<float>(off->items[1].n);
			}
			data.gateFacing = static_cast<float>(g->Num("facing", 0.0));
			if (auto refs = g->Get("refs"); refs && refs->IsArray()) {
				for (auto& r : refs->items) {
					auto ref = ResolveAs<RE::TESObjectREFR>(r.Get("id"), kDefaultPlugin, "gate ref");
					if (!ref) continue;
					GateRef gr;
					gr.id = ref->GetFormID();
					gr.dx = static_cast<float>(r.Num("dx", 0.0));
					gr.dy = static_cast<float>(r.Num("dy", 0.0));
					gr.dz = static_cast<float>(r.Num("dz", 0.0));
					gr.angle = static_cast<float>(r.Num("angle", 0.0));
					gr.door = r.Bool("door", false);
					data.gateRefs.push_back(gr);
				}
			}
			if (auto d = ResolveAs<RE::TESObjectREFR>(g->Get("door"), kDefaultPlugin, "gate door")) data.gateDoor = d->GetFormID();
			if (auto d = ResolveAs<RE::TESObjectREFR>(g->Get("arrivalDoor"), kDefaultPlugin, "arrival door")) data.arrivalDoor = d->GetFormID();
			data.gateItem = ResolveAs<RE::TESBoundObject>(g->Get("requiredItem"), "GravityGun.esp", "gate required item");
			data.gateDenied = g->Str("deniedMessage", "");
		}
		data.loaded = true;

		SKSE::log::info("forms.json: {} spawn groups, canister {}, headcrab kw {}, {} site cells, worldspace {}, {} actors, {} conversations, {} info actions, quest {}",
			data.groups.size(), data.canister != nullptr, data.headcrabKeyword != nullptr, data.siteCells.size(), data.siteWorldspace != nullptr,
			data.actors.size(), data.conversations.size(), data.infoActions.size(), data.quest != nullptr);
	}

	bool IsSiteCell(const RE::TESObjectCELL* a_cell)
	{
		if (!a_cell) return false;
		if (data.siteCells.contains(a_cell->GetFormID())) return true;
		return data.siteWorldspace && a_cell->IsExteriorCell() && a_cell->GetRuntimeData().worldSpace == data.siteWorldspace;
	}
}
