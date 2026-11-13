using UnrealBuildTool;

public class VigiliaTarget : TargetRules
{
	public VigiliaTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("Vigilia");
	}
}
