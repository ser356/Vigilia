#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VGInteractionComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FVGFocusChanged, AActor*, NewFocus);

/** Traza desde la camara del propietario y gestiona el foco y la interaccion. */
UCLASS(ClassGroup = (Vigilia), meta = (BlueprintSpawnableComponent))
class VIGILIA_API UVGInteractionComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UVGInteractionComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Interactua con el actor enfocado. Devuelve true si hubo interaccion. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Interaction")
	bool TryInteract();

	UFUNCTION(BlueprintPure, Category = "Vigilia|Interaction")
	AActor* GetFocusedActor() const { return FocusedActor.Get(); }

	UFUNCTION(BlueprintPure, Category = "Vigilia|Interaction")
	FText GetFocusedPrompt() const;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Interaction")
	void SetInteractionEnabled(bool bEnabled);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Interaction")
	float TraceDistance = 190.f;

	/** Radio del barrido de ayuda para objetos pequenos. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Interaction")
	float AssistRadius = 6.f;

	UPROPERTY(BlueprintAssignable, Category = "Vigilia|Interaction")
	FVGFocusChanged OnFocusChanged;

private:
	AActor* FindInteractable() const;
	static AActor* ResolveInteractable(AActor* HitActor);
	void SetFocus(AActor* NewFocus);

	TWeakObjectPtr<AActor> FocusedActor;
	bool bInteractionEnabled = true;
};
