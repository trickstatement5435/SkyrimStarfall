// Turns a nifkit static NIF into a weapon/item NIF: collision layer WEAPON, keyframed body (like the Gravity Gun world model),
// plus a "Prn" sheath node string. usage: item_fix in.nif out.nif <PrnNode or ->
#include "NifFile.hpp"
#include "bhk.hpp"
#include "ExtraData.hpp"
#include <cstdio>
using namespace nifly;
int main(int argc, char** argv)
{
	if (argc < 4) return 1;
	NifFile nif;
	if (nif.Load(argv[1]) != 0) return 1;
	auto& hdr = nif.GetHeader();
	int n = 0;
	for (uint32_t i = 0; i < hdr.GetNumBlocks(); ++i) {
		if (auto body = hdr.GetBlock<bhkRigidBody>(i)) {
			body->collisionFilter.layer = 5;   // OL_WEAPON
			body->collisionFilterCopy = body->collisionFilter;
			body->motionSystem = 6;            // MO_SYS_KEYFRAMED
			body->qualityType = 2;             // MO_QUAL_KEYFRAMED
			body->deactivatorType = 1;
			body->solverDeactivation = 1;
			body->mass = 0.0f;
			++n;
		}
	}
	if (std::string(argv[3]) != "-") {
		auto prn = std::make_unique<NiStringExtraData>();
		prn->name.get() = "Prn";
		prn->stringData.get() = argv[3];
		nif.AssignExtraData(nif.GetRootNode(), std::move(prn));
	}
	if (nif.Save(argv[2]) != 0) return 1;
	std::printf("item_fix: %d bodies -> %s\n", n, argv[2]);
	return 0;
}
