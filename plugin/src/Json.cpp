#include "Json.h"

namespace SF::Json
{
	const Value* Value::Get(std::string_view a_key) const
	{
		if (type != Type::kObject) {
			return nullptr;
		}
		for (std::size_t i = 0; i < keys.size() && i < items.size(); ++i) {
			if (keys[i] == a_key) {
				return &items[i];
			}
		}
		return nullptr;
	}

	double Value::Num(std::string_view a_key, double a_fallback) const
	{
		const auto v = Get(a_key);
		if (!v) return a_fallback;
		if (v->IsNumber()) return v->n;
		if (v->IsBool()) return v->b ? 1.0 : 0.0;
		return a_fallback;
	}

	bool Value::Bool(std::string_view a_key, bool a_fallback) const
	{
		const auto v = Get(a_key);
		if (!v) return a_fallback;
		if (v->IsBool()) return v->b;
		if (v->IsNumber()) return v->n != 0.0;
		return a_fallback;
	}

	std::string Value::Str(std::string_view a_key, std::string_view a_fallback) const
	{
		const auto v = Get(a_key);
		return (v && v->IsString()) ? v->s : std::string(a_fallback);
	}

	namespace
	{
		class Parser
		{
		public:
			explicit Parser(std::string_view a_text) : text(a_text) {}

			std::optional<Value> Run(std::string& a_error)
			{
				Value v;
				// tolerate a UTF-8 byte order mark
				if (text.size() >= 3 && static_cast<unsigned char>(text[0]) == 0xEF && static_cast<unsigned char>(text[1]) == 0xBB && static_cast<unsigned char>(text[2]) == 0xBF) {
					pos = 3;
				}
				if (!ParseValue(v, 0)) {
					a_error = std::format("line {}: {}", Line(), error);
					return std::nullopt;
				}
				SkipWs();
				if (pos != text.size()) {
					a_error = std::format("line {}: trailing characters", Line());
					return std::nullopt;
				}
				return v;
			}

		private:
			std::string_view text;
			std::size_t      pos = 0;
			std::string      error;

			std::size_t Line() const
			{
				return 1 + static_cast<std::size_t>(std::count(text.begin(), text.begin() + static_cast<std::ptrdiff_t>(std::min(pos, text.size())), '\n'));
			}

			bool Fail(std::string a_msg)
			{
				if (error.empty()) error = std::move(a_msg);
				return false;
			}

			void SkipWs()
			{
				while (pos < text.size()) {
					const char c = text[pos];
					if (c == ' ' || c == '\t' || c == '\r' || c == '\n') {
						++pos;
					} else {
						break;
					}
				}
			}

			bool Literal(std::string_view a_word)
			{
				if (text.substr(pos, a_word.size()) == a_word) {
					pos += a_word.size();
					return true;
				}
				return false;
			}

			static void AppendUtf8(std::string& a_out, std::uint32_t a_cp)
			{
				if (a_cp < 0x80) {
					a_out += static_cast<char>(a_cp);
				} else if (a_cp < 0x800) {
					a_out += static_cast<char>(0xC0 | (a_cp >> 6));
					a_out += static_cast<char>(0x80 | (a_cp & 0x3F));
				} else if (a_cp < 0x10000) {
					a_out += static_cast<char>(0xE0 | (a_cp >> 12));
					a_out += static_cast<char>(0x80 | ((a_cp >> 6) & 0x3F));
					a_out += static_cast<char>(0x80 | (a_cp & 0x3F));
				} else {
					a_out += static_cast<char>(0xF0 | (a_cp >> 18));
					a_out += static_cast<char>(0x80 | ((a_cp >> 12) & 0x3F));
					a_out += static_cast<char>(0x80 | ((a_cp >> 6) & 0x3F));
					a_out += static_cast<char>(0x80 | (a_cp & 0x3F));
				}
			}

			bool Hex4(std::uint32_t& a_out)
			{
				if (pos + 4 > text.size()) return Fail("bad \\u escape");
				a_out = 0;
				for (int i = 0; i < 4; ++i) {
					const char c = text[pos++];
					a_out <<= 4;
					if (c >= '0' && c <= '9') a_out |= static_cast<std::uint32_t>(c - '0');
					else if (c >= 'a' && c <= 'f') a_out |= static_cast<std::uint32_t>(c - 'a' + 10);
					else if (c >= 'A' && c <= 'F') a_out |= static_cast<std::uint32_t>(c - 'A' + 10);
					else return Fail("bad \\u escape");
				}
				return true;
			}

			bool ParseString(std::string& a_out)
			{
				++pos;  // opening quote
				while (pos < text.size()) {
					const char c = text[pos++];
					if (c == '"') {
						return true;
					}
					if (c != '\\') {
						a_out += c;
						continue;
					}
					if (pos >= text.size()) break;
					const char e = text[pos++];
					switch (e) {
					case '"': a_out += '"'; break;
					case '\\': a_out += '\\'; break;
					case '/': a_out += '/'; break;
					case 'b': a_out += '\b'; break;
					case 'f': a_out += '\f'; break;
					case 'n': a_out += '\n'; break;
					case 'r': a_out += '\r'; break;
					case 't': a_out += '\t'; break;
					case 'u':
						{
							std::uint32_t cp = 0;
							if (!Hex4(cp)) return false;
							// surrogate pair
							if (cp >= 0xD800 && cp <= 0xDBFF && text.substr(pos, 2) == "\\u") {
								pos += 2;
								std::uint32_t lo = 0;
								if (!Hex4(lo)) return false;
								cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
							}
							AppendUtf8(a_out, cp);
							break;
						}
					default:
						return Fail("bad escape in string");
					}
				}
				return Fail("unterminated string");
			}

			bool ParseNumber(double& a_out)
			{
				const auto start = pos;
				if (pos < text.size() && (text[pos] == '-' || text[pos] == '+')) ++pos;
				while (pos < text.size()) {
					const char c = text[pos];
					if ((c >= '0' && c <= '9') || c == '.' || c == 'e' || c == 'E' || c == '-' || c == '+') {
						++pos;
					} else {
						break;
					}
				}
				const std::string tmp(text.substr(start, pos - start));
				try {
					std::size_t used = 0;
					a_out = std::stod(tmp, &used);
					if (used != tmp.size()) return Fail("bad number");
				} catch (...) {
					return Fail("bad number");
				}
				return true;
			}

			bool ParseValue(Value& a_out, int a_depth)
			{
				if (a_depth > 64) return Fail("nesting too deep");
				SkipWs();
				if (pos >= text.size()) return Fail("unexpected end of file");
				const char c = text[pos];
				if (c == '{') {
					a_out.type = Value::Type::kObject;
					++pos;
					SkipWs();
					if (pos < text.size() && text[pos] == '}') {
						++pos;
						return true;
					}
					while (true) {
						SkipWs();
						if (pos >= text.size() || text[pos] != '"') return Fail("expected a key string");
						std::string key;
						if (!ParseString(key)) return false;
						SkipWs();
						if (pos >= text.size() || text[pos] != ':') return Fail("expected ':'");
						++pos;
						Value child;
						if (!ParseValue(child, a_depth + 1)) return false;
						a_out.keys.push_back(std::move(key));
						a_out.items.push_back(std::move(child));
						SkipWs();
						if (pos < text.size() && text[pos] == ',') {
							++pos;
							continue;
						}
						if (pos < text.size() && text[pos] == '}') {
							++pos;
							return true;
						}
						return Fail("expected ',' or '}'");
					}
				}
				if (c == '[') {
					a_out.type = Value::Type::kArray;
					++pos;
					SkipWs();
					if (pos < text.size() && text[pos] == ']') {
						++pos;
						return true;
					}
					while (true) {
						Value child;
						if (!ParseValue(child, a_depth + 1)) return false;
						a_out.items.push_back(std::move(child));
						SkipWs();
						if (pos < text.size() && text[pos] == ',') {
							++pos;
							continue;
						}
						if (pos < text.size() && text[pos] == ']') {
							++pos;
							return true;
						}
						return Fail("expected ',' or ']'");
					}
				}
				if (c == '"') {
					a_out.type = Value::Type::kString;
					return ParseString(a_out.s);
				}
				if (Literal("true")) {
					a_out.type = Value::Type::kBool;
					a_out.b = true;
					return true;
				}
				if (Literal("false")) {
					a_out.type = Value::Type::kBool;
					a_out.b = false;
					return true;
				}
				if (Literal("null")) {
					a_out.type = Value::Type::kNull;
					return true;
				}
				if (c == '-' || c == '+' || (c >= '0' && c <= '9')) {
					a_out.type = Value::Type::kNumber;
					return ParseNumber(a_out.n);
				}
				return Fail(std::format("unexpected character '{}'", c));
			}
		};
	}

	std::optional<Value> Parse(std::string_view a_text, std::string& a_error)
	{
		Parser p(a_text);
		return p.Run(a_error);
	}
}
