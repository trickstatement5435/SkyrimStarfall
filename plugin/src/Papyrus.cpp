#include "Starfall.h"

// Calling vanilla Papyrus natives (Say, SetLookAt, SetCurrentStageID, ...) from C++ by dispatching
// a method call on the form's script object, the same way GravityGun drives its quest.
// The call is queued in the VM and runs asynchronously (usually within the same frame).

namespace SF::Papyrus
{
	void CallOn(RE::VMTypeID a_type, const void* a_ptr, const char* a_class, const char* a_fn, RE::BSScript::IFunctionArguments* a_args)
	{
		auto vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm || !a_ptr) {
			delete a_args;
			return;
		}
		auto policy = vm->GetObjectHandlePolicy();
		if (!policy) {
			delete a_args;
			return;
		}
		const auto handle = policy->GetHandleForObject(a_type, a_ptr);
		RE::BSTSmartPointer<RE::BSScript::Object> obj;
		// The form may already carry an attached script (e.g. an Actor-derived script on the NPC);
		// otherwise bind a plain base-class object so the native can be called on it.
		if (!vm->FindBoundObject(handle, a_class, obj) || !obj) {
			if (vm->CreateObject(a_class, obj) && obj) {
				vm->BindObject(obj, handle, false);
			}
		}
		if (!obj) {
			SKSE::log::error("Couldn't bind a {} script object to call {}", a_class, a_fn);
			delete a_args;
			return;
		}
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;  // fire and forget
		vm->DispatchMethodCall(obj, a_fn, a_args, cb);
	}

	void CallActor(RE::Actor* a_actor, const char* a_fn, RE::BSScript::IFunctionArguments* a_args)
	{
		CallOn(static_cast<RE::VMTypeID>(RE::FormType::ActorCharacter), a_actor, "Actor", a_fn, a_args);
	}

	void CallRef(RE::TESObjectREFR* a_ref, const char* a_fn, RE::BSScript::IFunctionArguments* a_args)
	{
		if (a_ref && a_ref->As<RE::Actor>()) {
			CallActor(a_ref->As<RE::Actor>(), a_fn, a_args);
			return;
		}
		CallOn(static_cast<RE::VMTypeID>(RE::FormType::Reference), a_ref, "ObjectReference", a_fn, a_args);
	}

	void CallQuest(RE::TESQuest* a_quest, const char* a_fn, RE::BSScript::IFunctionArguments* a_args)
	{
		CallOn(static_cast<RE::VMTypeID>(RE::FormType::Quest), a_quest, "Quest", a_fn, a_args);
	}

	void Notify(const std::string& a_text)
	{
		auto vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm || a_text.empty()) return;
		RE::BSFixedString msg(a_text.c_str());
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
		// Debug.Notification(string asNotificationText): global native
		vm->DispatchStaticCall("Debug", "Notification", RE::MakeFunctionArguments(std::move(msg)), cb);
	}
}
