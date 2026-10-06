// prints every texture path referenced by the given NIFs: nif_textures a.nif b.nif ...
#include "NifFile.hpp"
#include <cstdio>
using namespace nifly;
int main(int argc, char** argv)
{
	for (int i = 1; i < argc; ++i) {
		NifFile nif;
		if (nif.Load(argv[i]) != 0) { std::printf("LOADFAIL %s\n", argv[i]); continue; }
		for (auto s : nif.GetShapes()) {
			for (uint32_t k = 0; k < 9; ++k) {
				std::string t;
				if (nif.GetTextureSlot(s, t, k) && !t.empty()) std::printf("%s\t%s\n", argv[i], t.c_str());
			}
		}
	}
	return 0;
}
