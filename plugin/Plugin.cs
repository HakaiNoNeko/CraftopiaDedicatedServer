using System;
using BepInEx;
using BepInEx.Configuration;
using HarmonyLib;

// Server-side only. The stock server never logs player chat (it travels over the OcNetRpc_Chat RPC), so
// this prints each client chat message to stdout as "[Chat] <netPlayerId>: <text>" for the manager to parse.
[BepInPlugin("hakai.craftopia.serverchat", "Craftopia Server Chat", "1.0.0")]
public class Plugin : BaseUnityPlugin
{
    static ConfigEntry<string> commandPrefix;
    static ConfigEntry<bool> hideCommands;

    void Awake()
    {
        commandPrefix = Config.Bind("Chat", "CommandPrefix", "!", "Messages starting with this are server commands.");
        hideCommands = Config.Bind("Chat", "HideCommands", true, "Do not broadcast command messages to other players.");
        var type = AccessTools.TypeByName("Oc.Network.OcNetRpc_Chat");
        var method = type == null ? null : AccessTools.Method(type, "ReceiveFromClient");
        if (method == null) { Logger.LogError("OcNetRpc_Chat.ReceiveFromClient not found; chat logging disabled"); return; }
        new Harmony("hakai.craftopia.serverchat").Patch(method, prefix: new HarmonyMethod(typeof(Plugin), nameof(Prefix)));
        Logger.LogInfo("Chat hook installed");
    }

    // __0 = the RequestChatMessage argument (Message, FromNetPlId, ToNetPlId)
    static bool Prefix(object __0)
    {
        try
        {
            var req = Traverse.Create(__0);
            var text = req.Field("Message").GetValue<string>() ?? "";
            var from = req.Field("FromNetPlId").GetValue<int>();
            // Debug.Log only reaches Unity's log file, not stdout, so write to stdout directly.
            Console.Out.WriteLine($"[Chat] {from}: {text.Replace('\n', ' ')}"); Console.Out.Flush();
            return !(hideCommands.Value && text.StartsWith(commandPrefix.Value, StringComparison.Ordinal));
        }
        catch (Exception e) { Console.Error.WriteLine("[ServerChat] " + e); return true; }
    }
}
