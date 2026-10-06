// static2nif: generic static-object NIF writer for Skyrim SE (nifly).
// Input is a small binary written by nifkit.py (see nifkit.py _pack for the exact layout):
//   shapes (BSTriShape + BSLightingShaderProperty or BSEffectShaderProperty, optional NiAlphaProperty)
//   + optional static Havok collision (bhkCollisionObject -> bhkRigidBody -> bhkListShape/bhkConvexVerticesShape).
// usage: static2nif in.bin out.nif
#include "NifFile.hpp"
#include "bhk.hpp"
#include "ExtraData.hpp"
#include "Shaders.hpp"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <stdexcept>
using namespace nifly;

// shape flags (keep in sync with nifkit.py)
enum : uint32_t {
	F_ALPHA_TEST = 1 << 0,
	F_ALPHA_BLEND = 1 << 1,
	F_DOUBLE_SIDED = 1 << 2,
	F_GLOW = 1 << 3,
	F_VCOLORS = 1 << 4,
	F_ADDITIVE = 1 << 5,      // effect shader: additive blending (src alpha, one), no depth write
	F_NO_SHADOWS = 1 << 6,    // do not cast/receive shadows
	F_DECAL = 1 << 7,         // SLSF1_DECAL (+ no shadows)
	F_ENVMAP = 1 << 8,        // envmap shader type, tex slots 4 (cube) and 5 (mask)
	F_NO_ZWRITE = 1 << 9,
	F_FALLOFF = 1 << 10,      // effect shader: use falloff angles
	F_VERTEX_ALPHA = 1 << 11,
};

struct Reader {
	std::ifstream in;
	explicit Reader(const char* p) : in(p, std::ios::binary) {
		if (!in) throw std::runtime_error("cannot open input");
	}
	template<class T> T rd() {
		T v{};
		in.read((char*)&v, sizeof v);
		if (!in) throw std::runtime_error("truncated input");
		return v;
	}
	std::string str() {
		uint16_t n = rd<uint16_t>();
		std::string s(n, '\0');
		if (n) in.read(s.data(), n);
		return s;
	}
	template<class T> void arr(T* dst, size_t n) {
		in.read((char*)dst, sizeof(T) * n);
		if (!in) throw std::runtime_error("truncated array");
	}
};

static const float HAVOK_SCALE = 0.0142875f;  // game units -> havok units (1 / 69.99125)

static void AddShape(NifFile& nif, Reader& r) {
	auto& hdr = nif.GetHeader();
	const std::string name = r.str();
	const uint8_t kind = r.rd<uint8_t>();  // 0 lighting, 1 effect
	const uint32_t flags = r.rd<uint32_t>();
	const uint32_t nv = r.rd<uint32_t>(), nt = r.rd<uint32_t>();
	const float spec = r.rd<float>(), gloss = r.rd<float>();
	float specCol[3]; r.arr(specCol, 3);
	float emit[3]; r.arr(emit, 3);
	const float emitMult = r.rd<float>();
	const float alpha = r.rd<float>();
	const uint8_t alphaThreshold = r.rd<uint8_t>();
	const float envScale = r.rd<float>();
	float baseCol[4]; r.arr(baseCol, 4);
	const float baseScale = r.rd<float>();
	float falloff[4]; r.arr(falloff, 4);
	const float softDepth = r.rd<float>();
	const float uvScale[2] = { r.rd<float>(), r.rd<float>() };
	const uint32_t ntex = r.rd<uint32_t>();
	std::vector<std::string> tex(ntex);
	for (auto& t : tex) t = r.str();

	std::vector<float> P(nv * 3), N(nv * 3), UV(nv * 2), C;
	r.arr(P.data(), P.size());
	r.arr(N.data(), N.size());
	r.arr(UV.data(), UV.size());
	if (flags & F_VCOLORS) { C.resize(nv * 4); r.arr(C.data(), C.size()); }
	std::vector<uint16_t> T(nt * 3);
	r.arr(T.data(), T.size());

	std::vector<Vector3> v(nv), n(nv);
	std::vector<Vector2> uv(nv);
	std::vector<Triangle> t(nt);
	for (uint32_t i = 0; i < nv; ++i) {
		v[i] = Vector3(P[i * 3], P[i * 3 + 1], P[i * 3 + 2]);
		n[i] = Vector3(N[i * 3], N[i * 3 + 1], N[i * 3 + 2]);
		uv[i] = Vector2(UV[i * 2], UV[i * 2 + 1]);
	}
	for (uint32_t i = 0; i < nt; ++i) t[i] = Triangle(T[i * 3], T[i * 3 + 1], T[i * 3 + 2]);

	NiShape* shape = nif.CreateShapeFromData(name, &v, &t, &uv, &n);
	if (!shape) throw std::runtime_error("CreateShapeFromData failed");
	nif.CalcTangentsForShape(shape);
	if (flags & F_VCOLORS) {
		std::vector<Color4> col(nv);
		for (uint32_t i = 0; i < nv; ++i) col[i] = Color4(C[i * 4], C[i * 4 + 1], C[i * 4 + 2], C[i * 4 + 3]);
		shape->SetVertexColors(true);
		nif.SetColorsForShape(shape, col);
	}

	if (kind == 0) {
		for (uint32_t k = 0; k < ntex && k < 9; ++k)
			if (!tex[k].empty()) { std::string tx = tex[k]; nif.SetTextureSlot(shape, tx, k); }
		auto sh = dynamic_cast<BSLightingShaderProperty*>(nif.GetShader(shape));
		if (!sh) throw std::runtime_error("no lighting shader");
		sh->shaderFlags1 = SLSF1_ZBUFFER_TEST | SLSF1_REMAPPABLE_TEXTURES;
		sh->shaderFlags2 = SLSF2_ZBUFFER_WRITE | SLSF2_ENVMAP_LIGHT_FADE;
		if (!(flags & (F_NO_SHADOWS | F_DECAL))) sh->shaderFlags1 |= SLSF1_RECEIVE_SHADOWS | SLSF1_CAST_SHADOWS;
		if (spec > 0.0f) sh->shaderFlags1 |= SLSF1_SPECULAR;
		sh->specularStrength = spec;
		sh->glossiness = gloss;
		sh->specularColor = Vector3(specCol[0], specCol[1], specCol[2]);
		sh->alpha = alpha;
		sh->uvScale = Vector2(uvScale[0], uvScale[1]);
		sh->emissiveColor = Vector3(emit[0], emit[1], emit[2]);
		sh->emissiveMultiple = emitMult;
		if (flags & F_DOUBLE_SIDED) sh->shaderFlags2 |= SLSF2_DOUBLE_SIDED;
		if (flags & F_VCOLORS) sh->shaderFlags2 |= SLSF2_VERTEX_COLORS;
		if (flags & F_VERTEX_ALPHA) sh->shaderFlags1 |= SLSF1_VERTEX_ALPHA;
		if (flags & F_DECAL) sh->shaderFlags1 |= SLSF1_DECAL;
		if (flags & F_NO_ZWRITE) sh->shaderFlags2 &= ~SLSF2_ZBUFFER_WRITE;
		if ((flags & F_GLOW) && ntex > 2 && !tex[2].empty()) {
			sh->SetShaderType(BSLSP_GLOWMAP);
			sh->shaderFlags2 |= SLSF2_GLOW_MAP;
			sh->shaderFlags1 |= SLSF1_OWN_EMIT;
		} else if ((flags & F_ENVMAP) && ntex > 4 && !tex[4].empty()) {
			sh->SetShaderType(BSLSP_ENVMAP);
			sh->shaderFlags1 |= SLSF1_ENVIRONMENT_MAPPING;
			sh->environmentMapScale = envScale;
		} else {
			sh->SetShaderType(BSLSP_DEFAULT);
			// a non-zero emissive colour without a glow map is still honoured with OWN_EMIT
			if (emit[0] + emit[1] + emit[2] > 0.0f && emitMult > 0.0f) sh->shaderFlags1 |= SLSF1_OWN_EMIT;
		}
	} else {
		// Effect shader: replace the lighting shader (and drop its texture set)
		auto old = dynamic_cast<BSLightingShaderProperty*>(nif.GetShader(shape));
		uint32_t shaderId = shape->ShaderPropertyRef()->index;
		uint32_t texSetId = old ? old->TextureSetRef()->index : NIF_NPOS;
		auto fx = std::make_unique<BSEffectShaderProperty>();
		fx->shaderFlags1 = SLSF1_ZBUFFER_TEST;
		fx->shaderFlags2 = SLSF2_ZBUFFER_WRITE;
		if (flags & (F_ADDITIVE | F_NO_ZWRITE)) fx->shaderFlags2 &= ~SLSF2_ZBUFFER_WRITE;
		if (flags & F_DOUBLE_SIDED) fx->shaderFlags2 |= SLSF2_DOUBLE_SIDED;
		if (flags & F_VCOLORS) fx->shaderFlags2 |= SLSF2_VERTEX_COLORS;
		if (flags & F_VERTEX_ALPHA) fx->shaderFlags1 |= SLSF1_VERTEX_ALPHA;
		if (flags & F_FALLOFF) fx->shaderFlags1 |= SLSF1_USE_FALLOFF;
		if (ntex > 0) fx->sourceTexture.get() = tex[0];
		if (ntex > 1 && !tex[1].empty()) {
			fx->greyscaleTexture.get() = tex[1];
			fx->shaderFlags1 |= SLSF1_GREYSCALETOPALETTE_COLOR;
		}
		fx->baseColor = Color4(baseCol[0], baseCol[1], baseCol[2], baseCol[3]);
		fx->baseColorScale = baseScale;
		fx->falloffStartAngle = falloff[0];
		fx->falloffStopAngle = falloff[1];
		fx->falloffStartOpacity = falloff[2];
		fx->falloffStopOpacity = falloff[3];
		fx->softFalloffDepth = softDepth;
		fx->uvScale = Vector2(uvScale[0], uvScale[1]);
		fx->textureClampMode = 3;  // WRAP_S_WRAP_T
		hdr.ReplaceBlock(shaderId, std::move(fx));
		if (texSetId != NIF_NPOS) hdr.DeleteBlock(texSetId);
	}

	if (flags & (F_ALPHA_TEST | F_ALPHA_BLEND | F_ADDITIVE)) {
		auto ap = std::make_unique<NiAlphaProperty>();
		if (flags & F_ADDITIVE)
			ap->flags = 0x100D;   // blend on, src SRC_ALPHA, dst ONE, test off
		else if (flags & F_ALPHA_BLEND)
			ap->flags = (flags & F_ALPHA_TEST) ? 0x12ED : 0x00ED;  // src SRC_ALPHA, dst INV_SRC_ALPHA (+ test GREATER)
		else
			ap->flags = 0x12EC;   // alpha test only (GREATER threshold)
		ap->threshold = alphaThreshold;
		nif.AssignAlphaProperty(shape, std::move(ap));
	}
}

static void AddCollision(NifFile& nif, Reader& r, uint32_t ncol) {
	auto& hdr = nif.GetHeader();
	auto root = nif.GetRootNode();
	std::vector<uint32_t> ids;
	for (uint32_t c = 0; c < ncol; ++c) {
		const uint32_t mat = r.rd<uint32_t>();
		const float radius = r.rd<float>();
		const uint32_t nvp = r.rd<uint32_t>(), npl = r.rd<uint32_t>();
		std::vector<float> V(nvp * 3), PL(npl * 4);
		r.arr(V.data(), V.size());
		r.arr(PL.data(), PL.size());
		auto cv = std::make_unique<bhkConvexVerticesShape>();
		cv->SetMaterial(mat);
		cv->radius = radius;
		for (uint32_t i = 0; i < nvp; ++i)
			{ Vector4 q(V[i * 3] * HAVOK_SCALE, V[i * 3 + 1] * HAVOK_SCALE, V[i * 3 + 2] * HAVOK_SCALE, 0.0f); cv->verts.push_back(q); }
		// planes: n.x + d <= 0 inside; d scales with the geometry
		for (uint32_t i = 0; i < npl; ++i)
			{ Vector4 q(PL[i * 4], PL[i * 4 + 1], PL[i * 4 + 2], PL[i * 4 + 3] * HAVOK_SCALE); cv->normals.push_back(q); }
		ids.push_back(hdr.AddBlock(std::move(cv)));
	}
	uint32_t topShape;
	if (ids.size() == 1) {
		topShape = ids[0];
	} else {
		auto list = std::make_unique<bhkListShape>();
		for (auto id : ids) list->subShapeRefs.AddBlockRef(id);
		auto first = hdr.GetBlock<bhkConvexVerticesShape>(ids[0]);
		list->SetMaterial(first ? first->GetMaterial() : 3741512247u);
		HavokFilter f;
		f.layer = 0;
		for (size_t i = 0; i < ids.size(); ++i) list->filters.push_back(f);
		topShape = hdr.AddBlock(std::move(list));
	}

	auto body = std::make_unique<bhkRigidBody>();
	body->shapeRef.index = topShape;
	body->collisionFilter.layer = 1;   // SKYL_STATIC
	body->collisionFilterCopy = body->collisionFilter;
	body->broadPhaseType = 1;
	body->prop.size = 0;
	body->rotation = QuaternionXYZW{ 0, 0, 0, 1 };
	body->center = Vector4(0, 0, 0, 0);
	body->mass = 0.0f;
	for (auto& x : body->inertiaMatrix) x = 0.0f;
	body->friction = 0.5f;
	body->restitution = 0.4f;
	body->motionSystem = 7;        // MO_SYS_FIXED
	body->deactivatorType = 1;     // DEACTIVATOR_NEVER
	body->solverDeactivation = 1;  // SOLVER_DEACTIVATION_OFF
	body->qualityType = 1;         // MO_QUAL_FIXED
	const uint32_t bodyId = hdr.AddBlock(std::move(body));

	auto col = std::make_unique<bhkCollisionObject>();
	col->flags = 0x81;  // ACTIVE | SYNC_ON_UPDATE (as in vanilla SSE statics)
	col->targetRef.index = nif.GetBlockID(root);
	col->bodyRef.index = bodyId;
	root->collisionRef.index = hdr.AddBlock(std::move(col));
}

int main(int argc, char** argv) {
	if (argc != 3) {
		std::printf("usage: static2nif in.bin out.nif\n");
		return 1;
	}
	try {
		Reader r(argv[1]);
		char magic[4];
		r.arr(magic, 4);
		if (std::memcmp(magic, "SNIF", 4) != 0) throw std::runtime_error("bad magic");
		const uint32_t ver = r.rd<uint32_t>();
		if (ver != 1) throw std::runtime_error("bad version");
		const std::string rootName = r.str();
		const int32_t bsx = r.rd<int32_t>();

		NifFile nif;
		nif.Create(NiVersion::getSSE());
		auto fade = std::make_unique<BSFadeNode>();
		fade->name.get() = rootName;
		nif.GetHeader().ReplaceBlock(0, std::move(fade));

		const uint32_t nshapes = r.rd<uint32_t>();
		for (uint32_t s = 0; s < nshapes; ++s) AddShape(nif, r);
		const uint32_t ncol = r.rd<uint32_t>();
		if (ncol) AddCollision(nif, r, ncol);

		if (bsx >= 0) {
			auto b = std::make_unique<BSXFlags>();
			b->name.get() = "BSX";
			b->integerData = (uint32_t)bsx;
			nif.AssignExtraData(nif.GetRootNode(), std::move(b));
		}

		nif.PrettySortBlocks();
		if (nif.Save(argv[2]) != 0) throw std::runtime_error("save failed");

		NifFile check;
		if (check.Load(argv[2]) != 0) throw std::runtime_error("reload failed");
		auto& h = check.GetHeader();
		size_t nCol = 0, nAlpha = 0, nFx = 0;
		size_t tv = 0, tt = 0;
		for (uint32_t i = 0; i < h.GetNumBlocks(); ++i) {
			auto b = h.GetBlock<NiObject>(i);
			if (!b) continue;
			std::string bn = b->GetBlockName();
			if (bn == "bhkConvexVerticesShape") ++nCol;
			if (bn == "NiAlphaProperty") ++nAlpha;
			if (bn == "BSEffectShaderProperty") ++nFx;
		}
		for (auto s : check.GetShapes()) { tv += s->GetNumVertices(); tt += s->GetNumTriangles(); }
		std::printf("OK %s shapes=%zu blocks=%u verts=%zu tris=%zu convex=%zu alpha=%zu effect=%zu\n", argv[2],
					check.GetShapes().size(), h.GetNumBlocks(), tv, tt, nCol, nAlpha, nFx);
	} catch (const std::exception& e) {
		std::printf("ERROR %s\n", e.what());
		return 1;
	}
	return 0;
}
