#include "VGLoopPortal.h"
#include "VGLoopSubsystem.h"
#include "VGStatics.h"
#include "VGDoor.h"
#include "Components/BoxComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"

AVGLoopPortal::AVGLoopPortal()
{
	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Box"));
	SetRootComponent(Box);
	Box->SetBoxExtent(FVector(40.f, 60.f, 100.f));
	Box->SetCollisionProfileName(TEXT("Trigger"));
	Box->SetGenerateOverlapEvents(true);
}

void AVGLoopPortal::BeginPlay()
{
	Super::BeginPlay();
	Box->OnComponentBeginOverlap.AddDynamic(this, &AVGLoopPortal::HandleOverlap);
}

void AVGLoopPortal::SetBoxExtent(FVector Extent)
{
	Box->Modify();
	Box->SetBoxExtent(Extent);
}

void AVGLoopPortal::SetDestination(AActor* InDestination)
{
	Modify();
	Destination = InDestination;
}

void AVGLoopPortal::HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	APawn* Pawn = Cast<APawn>(OtherActor);
	if (!Pawn || !Pawn->IsPlayerControlled() || !Destination)
	{
		return;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	if (Now - LastTeleport < 1.5)
	{
		return;
	}
	LastTeleport = Now;

	// Transformacion relativa: lo que el jugador tenia respecto al portal lo tendra respecto al destino.
	const FTransform From = GetActorTransform();
	const FTransform To = Destination->GetActorTransform();
	const FVector Local = From.InverseTransformPosition(Pawn->GetActorLocation());
	const float DeltaYaw = static_cast<float>(To.Rotator().Yaw - From.Rotator().Yaw);

	APlayerController* PC = Cast<APlayerController>(Pawn->GetController());
	if (PC && PC->PlayerCameraManager)
	{
		PC->PlayerCameraManager->SetManualCameraFade(1.f, FLinearColor::Black, false);
		PC->PlayerCameraManager->StartCameraFade(1.f, 0.f, FadeInTime, FLinearColor::Black, false, false);
	}

	Pawn->SetActorLocation(To.TransformPosition(Local), false, nullptr, ETeleportType::TeleportPhysics);
	if (PC)
	{
		FRotator Control = PC->GetControlRotation();
		Control.Yaw += DeltaYaw;
		PC->SetControlRotation(Control);
	}
	if (AVGDoor* Door = Cast<AVGDoor>(DoorToClose))
	{
		Door->CloseDoor(false);
	}
	if (TeleportSound)
	{
		UVGStatics::PlaySpatialSound(this, TeleportSound, To.GetLocation() - To.GetRotation().GetForwardVector() * 60.f, 0.8f, 1.f);
	}
	if (UVGLoopSubsystem* Loop = GetWorld()->GetSubsystem<UVGLoopSubsystem>())
	{
		Loop->AdvanceLoop();
	}
}
