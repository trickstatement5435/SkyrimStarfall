// Writes a skinned Skyrim SE NIF (armor / creature skin) from tools/pack.py output.
// usage: skin2nif in.bin out.nif
// per shape flags: 1 alpha test, 2 double sided, 4 glow map (slot 2), 8 alpha blend
#include "NifFile.hpp"
#include "Shaders.hpp"
#include "Skin.hpp"
#include <cstdio>
#include <fstream>
using namespace nifly;

static std::string ReadStr(std::ifstream& in)
{
	uint32_t n = 0;
	in.read((char*)&n, 4);
	std::string s(n, '\0');
	in.read(s.data(), n);
	return s;
}
template <class T> static T Rd(std::ifstream& in) { T v{}; in.read((char*)&v, sizeof v); return v; }

static MatTransform ReadXf(std::ifstream& in)
{
	float m[12];
	in.read((char*)m, sizeof m);  // rotation row-major 3x3 then translation
	MatTransform t;
	for (int r = 0; r < 3; ++r)
		for (int c = 0; c < 3; ++c) t.rotation[r][c] = m[r * 3 + c];
	t.translation = Vector3(m[9], m[10], m[11]);
	t.scale = 1.0f;
	return t;
}

int main(int argc, char** argv)
{
	if (argc < 3) return 1;
	std::ifstream in(argv[1], std::ios::binary);
	NifFile nif;
	nif.Create(NiVersion::getSSE());
	nif.GetRootNode()->name.get() = ReadStr(in);

	const uint32_t nb = Rd<uint32_t>(in);
	std::vector<std::string> boneNames(nb);
	std::vector<MatTransform> bindWorld(nb), skinToBone(nb);
	for (uint32_t b = 0; b < nb; ++b) {
		boneNames[b] = ReadStr(in);
		bindWorld[b] = ReadXf(in);
		skinToBone[b] = ReadXf(in);
	}
	// flat bone nodes under the root, at their bind pose (like vanilla armor)
	std::vector<int> boneIDs;
	for (uint32_t b = 0; b < nb; ++b) {
		NiNode* node = nif.AddNode(boneNames[b], bindWorld[b], nif.GetRootNode());
		boneIDs.push_back((int)nif.GetBlockID(node));
	}

	const uint32_t ns = Rd<uint32_t>(in);
	for (uint32_t s = 0; s < ns; ++s) {
		const std::string name = ReadStr(in);
		const std::string tex[6] = { ReadStr(in), ReadStr(in), ReadStr(in), ReadStr(in), ReadStr(in), ReadStr(in) };
		const float envScale = Rd<float>(in), specStrength = Rd<float>(in), gloss = Rd<float>(in);
		const uint32_t flags = Rd<uint32_t>(in);
		const float emitMult = Rd<float>(in);
		const uint32_t nv = Rd<uint32_t>(in), nt = Rd<uint32_t>(in), np = Rd<uint32_t>(in);
		NiVector<BSDismemberSkinInstance::PartitionInfo> parts;
		for (uint32_t p = 0; p < np; ++p) {
			BSDismemberSkinInstance::PartitionInfo pi;
			pi.flags = PartitionFlags(PF_EDITOR_VISIBLE | (p == 0 ? PF_START_NET_BONESET : 0));
			pi.partID = Rd<uint16_t>(in);
			parts.push_back(pi);
		}
		std::vector<Vector3> v(nv), n(nv);
		std::vector<Vector2> uv(nv);
		std::vector<std::array<uint8_t, 4>> bi(nv);
		std::vector<std::array<float, 4>> bw(nv);
		for (uint32_t i = 0; i < nv; ++i) {
			float d[8];
			in.read((char*)d, sizeof d);
			v[i] = Vector3(d[0], d[1], d[2]);
			n[i] = Vector3(d[3], d[4], d[5]);
			uv[i] = Vector2(d[6], d[7]);
			in.read((char*)bi[i].data(), 4);
			in.read((char*)bw[i].data(), 16);
		}
		std::vector<Triangle> t(nt);
		std::vector<int> triPart(nt);
		for (uint32_t i = 0; i < nt; ++i) {
			uint16_t a[3];
			in.read((char*)a, sizeof a);
			t[i] = Triangle(a[0], a[1], a[2]);
			triPart[i] = Rd<uint8_t>(in);
		}

		NiShape* shape = nif.CreateShapeFromData(name, &v, &t, &uv, &n);
		nif.CalcTangentsForShape(shape);
		nif.CreateSkinning(shape);
		nif.SetShapeBoneIDList(shape, boneIDs);
		for (uint32_t b = 0; b < nb; ++b) nif.SetShapeTransformSkinToBone(shape, b, skinToBone[b]);
		// Weights go into NiSkinData per bone: that's what UpdateSkinPartitions builds the game-facing
		// NiSkinPartition from (per-vertex BSTriShape weights alone leave the partitions empty).
		std::vector<std::unordered_map<uint16_t, float>> perBone(nb);
		for (uint32_t i = 0; i < nv; ++i)
			for (int k = 0; k < 4; ++k)
				if (bw[i][k] > 0.0f) perBone[bi[i][k]][(uint16_t)i] = bw[i][k];
		for (uint32_t b = 0; b < nb; ++b) {
			nif.SetShapeBoneWeights(name, b, perBone[b]);
			// bounding sphere of the bone's vertices, in bone space (used for culling)
			Vector3 c;
			int cnt = 0;
			for (auto& [vi, w] : perBone[b]) { c += v[vi]; ++cnt; }
			BoundingSphere bs;
			if (cnt) {
				c /= (float)cnt;
				float r = 0.0f;
				for (auto& [vi, w] : perBone[b]) r = std::max(r, (v[vi] - c).length());
				bs.center = skinToBone[b].ApplyTransform(c);
				bs.radius = r;
			}
			nif.SetShapeBoneBounds(name, b, bs);
		}
		for (uint32_t i = 0; i < nv; ++i) {
			std::vector<uint8_t> ids;
			std::vector<float> ws;
			for (int k = 0; k < 4; ++k)
				if (bw[i][k] > 0.0f) { ids.push_back(bi[i][k]); ws.push_back(bw[i][k]); }
			nif.SetShapeVertWeights(name, (uint16_t)i, ids, ws);
		}
		nif.SetShapePartitions(shape, parts, triPart, true);
		nif.UpdateSkinPartitions(shape);
		// Match vanilla SSE: every partition carries the full bone list, so the per-vertex bone numbers in the
		// shared vertex buffer (global indices) mean the same thing in every partition.
		{
			auto& hdr = nif.GetHeader();
			auto  si = hdr.GetBlock<NiSkinInstance>(shape->SkinInstanceRef());
			auto  sp = si ? hdr.GetBlock(si->skinPartitionRef) : nullptr;
			if (sp) {
				for (auto& part : sp->partitions) {
					part.bones.clear();
					for (uint32_t b = 0; b < nb; ++b) part.bones.push_back((uint16_t)b);
					part.numBones = (uint16_t)nb;
					for (size_t k = 0; k < part.vertexMap.size(); ++k) {
						const auto& vd = sp->vertData[part.vertexMap[k]];
						part.boneIndices[k] = BoneIndices{ vd.weightBones[0], vd.weightBones[1], vd.weightBones[2], vd.weightBones[3] };
					}
				}
				nif.UpdatePartitionFlags(shape);
			}
		}

		for (int k = 0; k < 6; ++k)
			if (!tex[k].empty()) { std::string tx = tex[k]; nif.SetTextureSlot(shape, tx, k); }
		if (auto sh = dynamic_cast<BSLightingShaderProperty*>(nif.GetShader(shape))) {
			sh->shaderFlags1 |= SLSF1_SKINNED | SLSF1_SPECULAR;
			if (!tex[4].empty()) {
				sh->SetShaderType(BSLSP_ENVMAP);
				sh->shaderFlags1 |= SLSF1_ENVIRONMENT_MAPPING;
				sh->environmentMapScale = envScale;
			}
			sh->specularStrength = specStrength;
			sh->glossiness = gloss;
			if (specStrength <= 0.0f) sh->shaderFlags1 &= ~SLSF1_SPECULAR;
			if (flags & 2) sh->shaderFlags2 |= SLSF2_DOUBLE_SIDED;
			if ((flags & 4) && !tex[2].empty()) {
				sh->SetShaderType(BSLSP_GLOWMAP);
				sh->shaderFlags2 |= SLSF2_GLOW_MAP;
				sh->shaderFlags1 |= SLSF1_OWN_EMIT;
				sh->SetEmissiveColor(Color4(1, 1, 1, 1));
				sh->SetEmissiveMultiple(emitMult);
			}
		}
		if (flags & (1 | 8)) {
			auto ap = std::make_unique<NiAlphaProperty>();
			ap->flags = (flags & 8) ? 0x12ED : 0x12EC;   // 0x12EC: alpha test only; 0x12ED: blend + test
			ap->threshold = 100;
			nif.AssignAlphaProperty(shape, std::move(ap));
		}
	}
	nif.PrettySortBlocks();
	if (nif.Save(argv[2]) != 0) return 1;
	NifFile check;
	if (check.Load(argv[2]) != 0) return 1;
	std::printf("%s: %zu shapes, %u blocks\n", argv[2], check.GetShapes().size(), check.GetHeader().GetNumBlocks());
	for (auto s : check.GetShapes()) {
		std::vector<std::string> bl;
		check.GetShapeBoneList(s, bl);
		NiVector<BSDismemberSkinInstance::PartitionInfo> pi;
		std::vector<int> tp;
		check.GetShapePartitions(s, pi, tp);
		std::printf("  %s: %zu bones, %u partitions\n", s->name.get().c_str(), bl.size(), (unsigned)pi.size());
	}
	return 0;
}
