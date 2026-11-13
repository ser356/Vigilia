#include "VGInteractionComponent.h"
#include "VGInteractable.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/Controller.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"

UVGInteractionComponent::UVGInteractionComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.05f;
}

void UVGInteractionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	SetFocus(bInteractionEnabled ? FindInteractable() : nullptr);
}

AActor* UVGInteractionComponent::ResolveInteractable(AActor* HitActor)
{
	// Sube por la jerarquia de attach para que piezas hijas (mallas extra) cuenten como su padre.
	for (AActor* A = HitActor; A != nullptr; A = A->GetAttachParentActor())
	{
		if (A->GetClass()->ImplementsInterface(UVGInteractable::StaticClass()))
		{
			return A;
		}
	}
	return nullptr;
}

AActor* UVGInteractionComponent::FindInteractable() const
{
	const APawn* Pawn = Cast<APawn>(GetOwner());
	const AController* Controller = Pawn ? Pawn->GetController() : nullptr;
	UWorld* World = GetWorld();
	if (!Controller || !World)
	{
		return nullptr;
	}

	FVector Start;
	FRotator Rot;
	Controller->GetPlayerViewPoint(Start, Rot);
	const FVector End = Start + Rot.Vector() * TraceDistance;

	FCollisionQueryParams Params(SCENE_QUERY_STAT(VGInteract), false, GetOwner());

	FHitResult Hit;
	if (World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
	{
		if (AActor* Found = ResolveInteractable(Hit.GetActor()))
		{
			return IVGInteractable::Execute_CanInteract(Found, GetOwner()) ? Found : nullptr;
		}
	}

	// Barrido fino: facilita apuntar a objetos pequenos sin atravesar paredes.
	if (AssistRadius > 0.f)
	{
		TArray<FHitResult> Hits;
		World->SweepMultiByChannel(Hits, Start, End, FQuat::Identity, ECC_Visibility,
			FCollisionShape::MakeSphere(AssistRadius), Params);
		for (const FHitResult& H : Hits)
		{
			AActor* Found = ResolveInteractable(H.GetActor());
			if (Found && IVGInteractable::Execute_CanInteract(Found, GetOwner()))
			{
				return Found;
			}
			if (H.bBlockingHit)
			{
				break;
			}
		}
	}
	return nullptr;
}

void UVGInteractionComponent::SetFocus(AActor* NewFocus)
{
	AActor* Old = FocusedActor.Get();
	if (Old == NewFocus)
	{
		return;
	}
	if (Old)
	{
		IVGInteractable::Execute_SetFocused(Old, false);
	}
	FocusedActor = NewFocus;
	if (NewFocus)
	{
		IVGInteractable::Execute_SetFocused(NewFocus, true);
	}
	OnFocusChanged.Broadcast(NewFocus);
}

bool UVGInteractionComponent::TryInteract()
{
	AActor* Target = FocusedActor.Get();
	if (!bInteractionEnabled || !Target)
	{
		return false;
	}
	if (!IVGInteractable::Execute_CanInteract(Target, GetOwner()))
	{
		return false;
	}
	IVGInteractable::Execute_Interact(Target, GetOwner());
	return true;
}

FText UVGInteractionComponent::GetFocusedPrompt() const
{
	if (AActor* Target = FocusedActor.Get())
	{
		return IVGInteractable::Execute_GetInteractionPrompt(Target, GetOwner());
	}
	return FText::GetEmpty();
}

void UVGInteractionComponent::SetInteractionEnabled(bool bEnabled)
{
	bInteractionEnabled = bEnabled;
	if (!bEnabled)
	{
		SetFocus(nullptr);
	}
}
