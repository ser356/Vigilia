#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "VGStatics.generated.h"

class USoundAttenuation;
class USoundBase;
class UStaticMesh;

UCLASS()
class VIGILIA_API UVGStatics : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Atenuacion espacial compartida para sonidos puntuales del escenario. */
	UFUNCTION(BlueprintPure, Category = "Vigilia|Audio")
	static USoundAttenuation* GetDefaultAttenuation();

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Audio", meta = (WorldContext = "WorldContextObject"))
	static void PlaySpatialSound(const UObject* WorldContextObject, USoundBase* Sound, FVector Location, float Volume = 1.f, float Pitch = 1.f);

	/**
	 * Centroide de los vertices de la malla (LOD0) en espacio local. Con TopFraction < 1 solo se
	 * consideran los vertices de la franja superior (p. ej. 0.2 = 20 % mas alto), lo que permite
	 * deducir donde esta el respaldo de un sofa. Lo usa el constructor de escenario para orientar muebles.
	 */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Editor")
	static FVector GetMeshVertexCentroid(UStaticMesh* Mesh, float TopFraction = 1.f);
};
