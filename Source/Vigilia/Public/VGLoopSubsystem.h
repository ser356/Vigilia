#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "VGLoopSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FVGLoopAdvanced, int32, LoopCount);

/** Estado global de la partida: vueltas al bucle del pasillo y mensajes en pantalla. */
UCLASS()
class VIGILIA_API UVGLoopSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Loop")
	void AdvanceLoop();

	UFUNCTION(BlueprintPure, Category = "Vigilia|Loop")
	int32 GetLoopCount() const { return LoopCount; }

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Loop")
	void ShowMessage(const FText& Text, float Duration);

	/** Mensaje visible ahora mismo (vacio si no hay ninguno). */
	FText GetMessage(float& OutAlpha) const;

	UPROPERTY(BlueprintAssignable, Category = "Vigilia|Loop")
	FVGLoopAdvanced OnLoopAdvanced;

private:
	int32 LoopCount = 0;
	FText Message;
	double MessageStart = 0.0;
	double MessageEnd = 0.0;
};
