#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VGEntity.generated.h"

class UStaticMeshComponent;
class USkeletalMeshComponent;
class USkeletalMesh;
class UAnimationAsset;
class UAudioComponent;
class UMaterialInterface;
class USoundBase;
class AVGLamp;

UENUM(BlueprintType)
enum class EVGEntityState : uint8
{
	Hidden,
	Watching,
	Chasing,
	Running
};

/**
 * La presencia de la casa: una silueta oscura que aparece a lo lejos, te observa y desaparece,
 * o te persigue a tirones y se desvanece al alcanzarte. No colisiona con nada.
 */
UCLASS()
class VIGILIA_API AVGEntity : public AActor
{
	GENERATED_BODY()

public:
	AVGEntity();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Malla y material de silueta. MeshYawOffset: giro para que el frente de la malla mire al jugador. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void SetupEntity(UStaticMesh* InMesh, UMaterialInterface* SilhouetteMaterial, FVector RelativeLocation, float InMeshYawOffset, float UniformScale);

	/** Cuerpo humanoide animado. Las animaciones pueden ser nulas (Run cae a Walk acelerado, etc.). */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void SetupSkeletal(USkeletalMesh* InMesh, UAnimationAsset* InIdle, UAnimationAsset* InWalk, UAnimationAsset* InRun, UMaterialInterface* SilhouetteMaterial, FVector RelativeLocation, float InMeshYawOffset, float UniformScale);

	/** Aparece en From y corre en linea recta hasta To; al llegar se esfuma. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void RunTo(FVector From, FVector To, float Speed);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void AddStepSound(USoundBase* Sound);

	/** Aparece de pie en Location (Z = suelo), mirando al jugador. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void Appear(FVector Location);

	/** Se queda mirando. Desaparece si te acercas a menos de VanishDistance o pasados MaxSeconds. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void Watch(float VanishDistance, float MaxSeconds);

	/** Te persigue en linea recta, avanzando a tirones. Si te alcanza: fundido a negro y desaparece. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void Chase(float Speed, float MaxSeconds);

	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void Vanish(bool bWithSound = false);

	/** Lamparas que parpadean cuando aparece o desaparece. */
	UFUNCTION(BlueprintCallable, Category = "Vigilia|Entity")
	void AddLinkedLamp(AVGLamp* Lamp);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<USkeletalMeshComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Vigilia")
	TObjectPtr<UAudioComponent> Audio;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	TObjectPtr<UAnimationAsset> IdleAnim;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	TObjectPtr<UAnimationAsset> WalkAnim;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	TObjectPtr<UAnimationAsset> RunAnim;

	/** Velocidad (cm/s) a la que la animacion de andar/correr se ve natural a ritmo 1. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	float WalkAnimSpeed = 110.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	float RunAnimSpeed = 420.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TArray<TObjectPtr<USoundBase>> StepSounds;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	float MeshYawOffset = 0.f;

	/** Distancia a la que "te alcanza" durante una persecucion (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	float CatchDistance = 75.f;

	/** Segundos entre cada tiron de movimiento (movimiento antinatural, no fluido). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Entity")
	float StepInterval = 0.16f;

	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Vigilia|Entity")
	TArray<TObjectPtr<AVGLamp>> LinkedLamps;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> AppearSound;

	/** Bucle que suena mientras persigue. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> ChaseLoopSound;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vigilia|Audio")
	TObjectPtr<USoundBase> CatchSound;

private:
	void FacePlayer();
	void FaceDirection(const FVector& Direction);
	void PlayAnim(UAnimationAsset* Anim, float Rate);
	void PlayMoveAnim(float Speed);
	void Footsteps(float MovedDistance);
	bool HasBody() const;

	FVector RunTarget = FVector::ZeroVector;
	float RunSpeed = 0.f;
	float StepAccumulator = 0.f;
	void FlickerLamps(float Duration);
	APawn* GetPlayer() const;

	EVGEntityState State = EVGEntityState::Hidden;
	float TimeLeft = 0.f;
	float WatchVanishDistance = 0.f;
	float ChaseSpeed = 0.f;
	float StepTimer = 0.f;
	float PendingAdvance = 0.f;
};
