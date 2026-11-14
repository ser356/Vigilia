#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VGDustMotes.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;

/**
 * Motas de polvo en suspension alrededor del jugador. Son particulas iluminadas por las luces de la
 * escena: solo se ven donde hay luz (haz de la linterna, resplandor de la tele, la ventana).
 * Simuladas en CPU sobre mallas instanciadas: sin dependencias de plugins y con coste minimo.
 */
UCLASS()
class VIGILIA_API AVGDustMotes : public AActor
{
	GENERATED_BODY()

public:
	AVGDustMotes();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Dust")
	void SetupDust(UStaticMesh* InMesh, UMaterialInterface* InMaterial, int32 InCount, FVector InBoxExtent, float InMoteSize);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UInstancedStaticMeshComponent> Motes;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Dust")
	int32 Count = 350;

	/** Semiejes de la caja (centrada en la camara) en la que flotan las motas. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Dust")
	FVector BoxExtent = FVector(260.f, 260.f, 130.f);

	/** Diametro medio de una mota (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Dust")
	float MoteSize = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Dust")
	float DriftSpeed = 2.2f;

private:
	struct FMote
	{
		FVector Offset;
		FVector Velocity;
		float Scale;
		float Phase;
	};
	TArray<FMote> Data;
	float MeshRadius = 50.f;
};
