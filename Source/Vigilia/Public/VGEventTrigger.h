#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VGEventTrigger.generated.h"

class UBoxComponent;
class AVGEventTrigger;
class USoundBase;

UENUM(BlueprintType)
enum class EVGEventAction : uint8
{
	LampOn,
	LampOff,
	LampFlicker,
	TVOn,
	TVOff,
	DoorOpen,
	DoorClose,
	DoorSlam,
	/** Reproduce Sound en la posicion del Target (o del trigger si no hay Target). */
	PlaySound,
	/** Aplica Offset (posicion relativa + rotacion) al Target. */
	MoveActor,
	ToggleVisibility,
	/** Arranca / para el audio del Target (p. ej. el tic-tac del reloj de pie). */
	AudioPlay,
	AudioStop,
	/** Reproduce Sound justo detras de la cabeza del jugador. Offset.X = distancia (cm, por defecto 70). */
	SoundBehindPlayer,
	/** Hace sonar un AVGPhone. */
	PhoneRing,
	/** Dispara otro AVGEventTrigger (para encadenar secuencias). */
	FireTrigger,
	/** Gira el Target (solo en horizontal) para que mire al jugador. */
	FacePlayer,
	/** La linterna del jugador parpadea y se apaga. Offset.X = duracion en segundos (por defecto 3). */
	FlashlightFail,
	DoorLock,
	DoorUnlock,
	/** Cambia el color de una lampara: Offset.Scale = RGB. */
	LampColor,
	/** Muestra Message en pantalla. Offset.X = duracion (por defecto 4 s). */
	ShowMessage,
	/** La entidad (Target) aparece en Offset.Location (coordenadas de mundo, Z = suelo). */
	EntityAppear,
	/** La entidad se queda mirando. Offset.X = distancia a la que se esfuma, Offset.Y = segundos maximos. */
	EntityWatch,
	/** La entidad persigue al jugador. Offset.X = velocidad (cm/s), Offset.Y = segundos maximos. */
	EntityChase,
	EntityVanish
};

USTRUCT(BlueprintType)
struct FVGEventStep
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia")
	EVGEventAction Action = EVGEventAction::PlaySound;

	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Vigilia")
	TObjectPtr<AActor> Target;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia")
	float Delay = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia")
	TObjectPtr<USoundBase> Sound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia")
	FTransform Offset;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia", meta = (MultiLine = true))
	FText Message;

	/** Espera a que el jugador NO este mirando al Target para ejecutarse (reintenta hasta 40 s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia")
	bool bOnlyWhenUnseen = false;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FVGEventTriggered, AVGEventTrigger*, Trigger);

/** Volumen que lanza una secuencia de pasos de evento cuando el jugador lo atraviesa. */
UCLASS()
class VIGILIA_API AVGEventTrigger : public AActor
{
	GENERATED_BODY()

public:
	AVGEventTrigger();

	virtual void BeginPlay() override;

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Events")
	void AddStep(EVGEventAction Action, AActor* Target, float Delay, USoundBase* Sound, FTransform Offset, bool bOnlyWhenUnseen);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Events")
	void SetBoxExtent(FVector Extent);

	/** Paso con texto (para ShowMessage). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Events")
	void AddMessageStep(float Delay, const FText& Text, float Duration);

	/** Fuerza el evento (tambien util desde consola o Blueprints). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Events")
	void Fire();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UBoxComponent> Box;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	TArray<FVGEventStep> Steps;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	bool bOnce = true;

	/** Probabilidad de dispararse en cada entrada (0-1). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events", meta = (ClampMin = "0", ClampMax = "1"))
	float Chance = 1.f;

	/** No se dispara hasta que haya pasado este tiempo de partida (segundos). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	float MinGameTime = 0.f;

	/** Si es >= 0, se dispara solo a los N segundos de partida (sin necesidad de pisar el volumen). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	float AutoFireAfter = -1.f;

	/** Con AutoFireAfter: espera a que el jugador este dentro del volumen (reintenta cada 4 s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	bool bRequirePlayerInside = false;

	/** Si es >= 0, se dispara al completar esa vuelta del bucle del pasillo (1 = primera vuelta). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	int32 RequiredLoop = -1;

	/** Si es > 0, tras dispararse se vuelve a disparar cada N segundos (comportamientos persistentes). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	float RepeatInterval = 0.f;

	/** Si es false, pisar el volumen no lo dispara (solo AutoFire o Fire()). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	bool bFireOnOverlap = true;

	/** Numero de entradas al volumen necesarias antes de poder dispararse. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Events")
	int32 RequiredEntries = 1;

	UPROPERTY(BlueprintAssignable, Category = "Vigilia|Events")
	FVGEventTriggered OnTriggered;

private:
	UFUNCTION()
	void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	void ExecuteStep(int32 Index);
	void ExecuteStepWhenUnseen(int32 Index, int32 Attempt);
	void TryAutoFire();

	UFUNCTION()
	void HandleLoop(int32 LoopCount);
	bool IsPlayerInside() const;
	bool IsSeenByPlayer(const AActor* Target) const;

	bool bFired = false;
	int32 Entries = 0;
};
