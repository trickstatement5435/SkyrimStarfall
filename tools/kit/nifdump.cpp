// nifdump: inspect a NIF (block list, shader flags, collision params) and optionally dump geometry
// usage: nifdump in.nif [geom_out.bin]
//   geom_out.bin: u32 nshapes; per shape: u16 namelen,name, u32 nv, nt, f32 P[nv*3], N[nv*3], UV[nv*2], u16 T[nt*3]
//                 then u32 nconvex; per convex: u32 mat, u32 nv, f32 V[nv*3] (game units)
#include "NifFile.hpp"
#include "bhk.hpp"
#include "ExtraData.hpp"
#include "Shaders.hpp"
#include <cstdio>
#include <fstream>
using namespace nifly;

int main(int argc, char** argv) {
	if (argc < 2) return 1;
	NifFile nif;
	if (nif.Load(argv[1]) != 0) { std::printf("load failed\n"); return 1; }
	auto& h = nif.GetHeader();
	std::printf("%s: %u blocks\n", argv[1], h.GetNumBlocks());
	for (uint32_t i = 0; i < h.GetNumBlocks(); ++i) {
		auto b = h.GetBlock<NiObject>(i);
		if (!b) continue;
		std::printf("  [%u] %s", i, b->GetBlockName());
		if (auto x = dynamic_cast<BSXFlags*>(b)) std::printf(" BSX=%u", x->integerData);
		if (auto s = dynamic_cast<BSLightingShaderProperty*>(b))
			std::printf(" type=%u f1=%08X f2=%08X spec=%.2f gloss=%.1f emit=(%.2f %.2f %.2f)x%.2f alpha=%.2f", s->GetShaderType(), s->shaderFlags1, s->shaderFlags2,
						s->specularStrength, s->glossiness, s->emissiveColor.x, s->emissiveColor.y, s->emissiveColor.z, s->emissiveMultiple, s->alpha);
		if (auto s = dynamic_cast<BSEffectShaderProperty*>(b))
			std::printf(" f1=%08X f2=%08X src=%s base=(%.2f %.2f %.2f %.2f)x%.2f", s->shaderFlags1, s->shaderFlags2, s->sourceTexture.get().c_str(),
						s->baseColor.r, s->baseColor.g, s->baseColor.b, s->baseColor.a, s->baseColorScale);
		if (auto a = dynamic_cast<NiAlphaProperty*>(b)) std::printf(" flags=%04X thr=%u", a->flags, a->threshold);
		if (auto ts = dynamic_cast<BSShaderTextureSet*>(b)) {
			for (auto& t : ts->textures) if (!t.get().empty()) std::printf(" [%s]", t.get().c_str());
		}
		if (auto c = dynamic_cast<bhkCollisionObject*>(b)) std::printf(" flags=%u", c->flags);
		if (auto r = dynamic_cast<bhkRigidBody*>(b))
			std::printf(" layer=%u fp=%u grp=%u motion=%u qual=%u deact=%u solver=%u mass=%.2f fr=%.2f rest=%.2f bp=%u resp=%u cb=%u bodyFlags=%u",
						r->collisionFilter.layer, r->collisionFilter.flagsAndParts, r->collisionFilter.group, r->motionSystem, r->qualityType,
						r->deactivatorType, r->solverDeactivation, r->mass, r->friction, r->restitution, r->broadPhaseType, r->collisionResponse,
						r->processContactCallbackDelay, r->bodyFlags);
		if (auto l = dynamic_cast<bhkListShape*>(b)) {
			std::printf(" n=%u mat=%u filters=%zu", l->subShapeRefs.GetSize(), l->GetMaterial(), l->filters.size());
			for (auto& f : l->filters) std::printf(" (%u,%u,%u)", f.layer, f.flagsAndParts, f.group);
		}
		if (auto cv = dynamic_cast<bhkConvexVerticesShape*>(b))
			std::printf(" mat=%u r=%.4f nv=%zu np=%zu", cv->GetMaterial(), cv->radius, cv->verts.size(), cv->normals.size());
		if (auto m = dynamic_cast<bhkMoppBvTreeShape*>(b)) (void)m;
		if (auto s = dynamic_cast<BSTriShape*>(b)) std::printf(" '%s' nv=%u nt=%u", s->name.get().c_str(), s->GetNumVertices(), s->GetNumTriangles());
		std::printf("\n");
	}
	if (argc < 3) return 0;
	std::ofstream o(argv[2], std::ios::binary);
	auto shapes = nif.GetShapes();
	uint32_t ns = (uint32_t)shapes.size();
	o.write((char*)&ns, 4);
	for (auto s : shapes) {
		std::vector<Vector3> v, n;
		std::vector<Vector2> uv;
		std::vector<Triangle> t;
		nif.GetVertsForShape(s, v);
		if (auto nn = nif.GetNormalsForShape(s)) n = *nn; else n.assign(v.size(), Vector3());
		if (auto uu = nif.GetUvsForShape(s)) uv = *uu; else uv.assign(v.size(), Vector2());
		s->GetTriangles(t);
		auto xf = s->GetTransformToParent();  // shapes sit directly under the root in our files
		for (auto& p : v) p = xf.ApplyTransform(p);
		std::string nm = s->name.get();
		uint16_t l = (uint16_t)nm.size();
		o.write((char*)&l, 2); o.write(nm.data(), l);
		// texture + render flags: 1 alpha property, 2 blending, 4 double sided, 8 effect shader, 16 glow map shader, 32 additive
		std::string t0, t2;
		uint32_t rf = 0;
		auto shader = nif.GetShader(s);
		if (auto ls = dynamic_cast<BSLightingShaderProperty*>(shader)) {
			nif.GetTextureSlot(s, t0, 0);
			nif.GetTextureSlot(s, t2, 2);
			if (ls->shaderFlags2 & SLSF2_DOUBLE_SIDED) rf |= 4;
			if (ls->GetShaderType() == BSLSP_GLOWMAP) rf |= 16;
		}
		if (auto es = dynamic_cast<BSEffectShaderProperty*>(shader)) {
			t0 = es->sourceTexture.get();
			rf |= 8;
			if (es->shaderFlags2 & SLSF2_DOUBLE_SIDED) rf |= 4;
		}
		if (auto ap = nif.GetAlphaProperty(s)) {
			rf |= 1;
			if (ap->flags & 1) rf |= 2;
			if ((ap->flags & 1) && ((ap->flags >> 5) & 15) == 0) rf |= 32;
		}
		for (auto* str : { &t0, &t2 }) { uint16_t ln = (uint16_t)str->size(); o.write((char*)&ln, 2); o.write(str->data(), ln); }
		o.write((char*)&rf, 4);
		// effect base colour * scale (1 for lit shapes) and material alpha
		float ec[5] = { 1, 1, 1, 1, 1 };
		if (auto es = dynamic_cast<BSEffectShaderProperty*>(shader)) {
			ec[0] = es->baseColor.r * es->baseColorScale; ec[1] = es->baseColor.g * es->baseColorScale;
			ec[2] = es->baseColor.b * es->baseColorScale; ec[3] = es->baseColor.a;
		}
		if (auto ls = dynamic_cast<BSLightingShaderProperty*>(shader)) ec[4] = ls->alpha;
		o.write((char*)ec, sizeof ec);
		uint32_t nv = (uint32_t)v.size(), nt = (uint32_t)t.size();
		o.write((char*)&nv, 4); o.write((char*)&nt, 4);
		for (auto& p : v) o.write((char*)&p, 12);
		for (auto& p : n) o.write((char*)&p, 12);
		for (auto& p : uv) o.write((char*)&p, 8);
		for (auto& p : t) { uint16_t q[3] = { p.p1, p.p2, p.p3 }; o.write((char*)q, 6); }
	}
	std::vector<bhkConvexVerticesShape*> cvs;
	for (uint32_t i = 0; i < h.GetNumBlocks(); ++i)
		if (auto cv = h.GetBlock<bhkConvexVerticesShape>(i)) cvs.push_back(cv);
	uint32_t nc = (uint32_t)cvs.size();
	o.write((char*)&nc, 4);
	for (auto cv : cvs) {
		uint32_t mat = cv->GetMaterial(), nv = (uint32_t)cv->verts.size();
		o.write((char*)&mat, 4); o.write((char*)&nv, 4);
		for (auto& p : cv->verts) { float q[3] = { p.x / 0.0142875f, p.y / 0.0142875f, p.z / 0.0142875f }; o.write((char*)q, 12); }
	}
	return 0;
}
