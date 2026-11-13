#include "VGStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "UObject/Package.h"

USoundAttenuation* UVGStatics::GetDefaultAttenuation()
{
	static TWeakObjectPtr<USoundAttenuation> Cached;
	if (!Cached.IsValid())
	{
		USoundAttenuation* Att = NewObject<USoundAttenuation>(GetTransientPackage(), TEXT("VG_DefaultAttenuation"));
		Att->Attenuation.bSpatialize = true;
		Att->Attenuation.bAttenuate = true;
		Att->Attenuation.FalloffDistance = 1500.f;
		Att->Attenuation.AttenuationShapeExtents = FVector(140.f);
		// Oclusion: a traves de paredes y puertas cerradas el sonido se apaga y pierde agudos.
		Att->Attenuation.bEnableOcclusion = true;
		Att->Attenuation.OcclusionTraceChannel = ECC_Visibility;
		Att->Attenuation.OcclusionLowPassFilterFrequency = 700.f;
		Att->Attenuation.OcclusionVolumeAttenuation = 0.35f;
		Att->Attenuation.OcclusionInterpolationTime = 0.25f;
		Att->Attenuation.bEnableReverbSend = true;

		Att->AddToRoot();
		Cached = Att;
	}
	return Cached.Get();
}

void UVGStatics::PlaySpatialSound(const UObject* WorldContextObject, USoundBase* Sound, FVector Location, float Volume, float Pitch)
{
	if (Sound)
	{
		UGameplayStatics::PlaySoundAtLocation(WorldContextObject, Sound, Location, Volume, Pitch, 0.f, GetDefaultAttenuation());
	}
}

FVector UVGStatics::GetMeshVertexCentroid(UStaticMesh* Mesh, float TopFraction)
{
	if (!Mesh || !Mesh->GetRenderData() || Mesh->GetRenderData()->LODResources.Num() == 0)
	{
		return FVector::ZeroVector;
	}

	const FPositionVertexBuffer& Positions = Mesh->GetRenderData()->LODResources[0].VertexBuffers.PositionVertexBuffer;
	const uint32 Count = Positions.GetNumVertices();
	if (Count == 0)
	{
		return FVector::ZeroVector;
	}

	const FBox Box = Mesh->GetBoundingBox();
	const float MinZ = Box.Max.Z - Box.GetSize().Z * FMath::Clamp(TopFraction, 0.01f, 1.f);

	FVector Sum = FVector::ZeroVector;
	uint32 Used = 0;
	for (uint32 Index = 0; Index < Count; ++Index)
	{
		const FVector P(Positions.VertexPosition(Index));
		if (P.Z >= MinZ)
		{
			Sum += P;
			++Used;
		}
	}
	return Used > 0 ? Sum / static_cast<double>(Used) : Box.GetCenter();
}
