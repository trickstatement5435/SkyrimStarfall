#pragma once

// Tiny JSON reader for forms.json. Only what the data contract needs:
// objects, arrays, strings (with the usual escapes), numbers, true/false/null.
// Kept in-tree so the plugin has no extra vcpkg dependency.

namespace SF::Json
{
	struct Value
	{
		enum class Type
		{
			kNull,
			kBool,
			kNumber,
			kString,
			kArray,
			kObject
		};

		Type                     type = Type::kNull;
		bool                     b = false;
		double                   n = 0.0;
		std::string              s;
		std::vector<Value>       items;  // array elements, or object values
		std::vector<std::string> keys;   // object keys (same order as items)

		[[nodiscard]] bool IsNull() const { return type == Type::kNull; }
		[[nodiscard]] bool IsObject() const { return type == Type::kObject; }
		[[nodiscard]] bool IsArray() const { return type == Type::kArray; }
		[[nodiscard]] bool IsString() const { return type == Type::kString; }
		[[nodiscard]] bool IsNumber() const { return type == Type::kNumber; }
		[[nodiscard]] bool IsBool() const { return type == Type::kBool; }

		// Object member lookup; nullptr when missing or not an object
		[[nodiscard]] const Value* Get(std::string_view a_key) const;

		// Lenient getters: return the fallback when missing or of the wrong type
		[[nodiscard]] double      Num(std::string_view a_key, double a_fallback) const;
		[[nodiscard]] bool        Bool(std::string_view a_key, bool a_fallback) const;
		[[nodiscard]] std::string Str(std::string_view a_key, std::string_view a_fallback) const;
	};

	// Returns nullopt on a syntax error and fills a_error with "line N: message"
	std::optional<Value> Parse(std::string_view a_text, std::string& a_error);
}
