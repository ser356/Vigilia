using UnrealBuildTool;

public class VigiliaEditorTarget : TargetRules
{
	public VigiliaEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("Vigilia");
	}
}
