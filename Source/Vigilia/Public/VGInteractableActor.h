#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VGInteractable.h"
#include "VGInteractableActor.generated.h"

class UStaticMeshComponent;
class UAudioComponent;
class USoundBase;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FVGInteracted, AActor*, Source, AActor*, Interactor);

/** Base reutilizable: raiz + malla + audio espacial + implementacion por defecto de la interfaz. */
UCLASS(Abstract)
class VIGILIA_API AVGInteractableActor : public AActor, public IVGInteractable
{
	GENERATED_BODY()

public:
	AVGInteractableActor();

	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual bool CanInteract_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;
	virtual void SetFocused_Implementation(bool bFocused) override;

	/** Asigna la malla principal (lo usa el constructor de escenario en Python). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia")
	virtual void SetupMesh(UStaticMesh* InMesh, FVector RelativeLocation, FRotator RelativeRotation);

	UFUNCTION(BlueprintCallable, Category = "Vigilia")
	void SetInteractionEnabled(bool bEnabled) { bInteractionEnabled = bEnabled; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Interaction")
	FText Prompt;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Interaction")
	bool bInteractionEnabled = true;

	UPROPERTY(BlueprintAssignable, Category = "Vigilia|Interaction")
	FVGInteracted OnInteracted;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UAudioComponent> Audio;

protected:
	void PlayLocalSound(USoundBase* Sound, float Volume = 1.f, float Pitch = 1.f);
};
