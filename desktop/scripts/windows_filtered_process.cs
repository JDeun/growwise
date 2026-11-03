// CI-only launcher. No machine policy, credentials, or application configuration changes.
// https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-createprocesswithtokenw
// https://learn.microsoft.com/windows/win32/api/winsafer/nf-winsafer-safercomputetokenfromlevel
using System;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;

namespace GrowWiseNativeToken {
    public sealed class TokenInfo {
        public string UserSid;
        public string IntegritySid;
        public uint IntegrityRid;
        public bool IsElevated;
        public int ElevationType;
        public bool AdministratorsEnabled;
    }

    public sealed class LaunchDiagnostics {
        public string Source;
        public int WithTokenError;
        public string WithTokenMessage;
        public int? AsUserError;
        public string AsUserMessage;
        public Dictionary<string, string> BootstrapPrivileges;
        public string FilteredIntegritySid;
        public bool FilteredIsElevated;
        public bool FilteredAdministratorsEnabled;
    }

    public sealed class LaunchedProcess : IDisposable {
        internal IntPtr Handle;
        public uint ProcessId;
        public string Source;
        public TokenInfo Token;
        public int WaitForExit() { return WaitForExit(180000); }
        public int WaitForExit(uint milliseconds) {
            uint wait = Native.WaitForSingleObject(Handle, milliseconds);
            if (wait == 258) {
                Native.TerminateProcess(Handle, 1);
                Native.WaitForSingleObject(Handle, 5000);
                throw new TimeoutException("Owned filtered E2E worker timed out.");
            }
            if (wait != 0) throw new Win32Exception(Marshal.GetLastWin32Error());
            uint code;
            if (!Native.GetExitCodeProcess(Handle, out code)) throw new Win32Exception();
            return unchecked((int)code);
        }
        public void Dispose() {
            if (Handle != IntPtr.Zero) {
                if (Native.WaitForSingleObject(Handle, 0) == 258) {
                    Native.TerminateProcess(Handle, 1);
                    Native.WaitForSingleObject(Handle, 5000);
                }
                Native.CloseHandle(Handle); Handle = IntPtr.Zero;
            }
        }
    }

    internal static class Native {
        [StructLayout(LayoutKind.Sequential)] internal struct SidAttributes { public IntPtr Sid; public uint Attributes; }
        [StructLayout(LayoutKind.Sequential)] internal struct Groups { public uint Count; public SidAttributes First; }
        [StructLayout(LayoutKind.Sequential)] internal struct Luid { public uint Low; public int High; }
        [StructLayout(LayoutKind.Sequential)] internal struct LuidAttributes { public Luid Value; public uint Attributes; }
        [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] internal struct StartupInfo {
            public uint cb; public string reserved; public string desktop; public string title;
            public uint x, y, xSize, ySize, xChars, yChars, fillAttribute, flags;
            public ushort showWindow, reservedSize; public IntPtr reservedBytes, stdin, stdout, stderr;
        }
        [StructLayout(LayoutKind.Sequential)] internal struct ProcessInfo {
            public IntPtr Process, Thread; public uint ProcessId, ThreadId;
        }
        [DllImport("kernel32.dll")] internal static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll", SetLastError=true)] internal static extern bool CloseHandle(IntPtr value);
        [DllImport("kernel32.dll", SetLastError=true)] internal static extern uint WaitForSingleObject(IntPtr value, uint milliseconds);
        [DllImport("kernel32.dll", SetLastError=true)] internal static extern bool GetExitCodeProcess(IntPtr process, out uint code);
        [DllImport("kernel32.dll", SetLastError=true)] internal static extern bool TerminateProcess(IntPtr process, uint code);
        [DllImport("kernel32.dll", SetLastError=true)] internal static extern uint ResumeThread(IntPtr thread);
        [DllImport("advapi32.dll", SetLastError=true)] internal static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
        [DllImport("advapi32.dll", SetLastError=true)] internal static extern bool GetTokenInformation(IntPtr token, int kind, IntPtr data, uint size, out uint needed);
        [DllImport("advapi32.dll", SetLastError=true)] internal static extern bool SetTokenInformation(IntPtr token, int kind, ref SidAttributes data, uint size);
        [DllImport("advapi32.dll", SetLastError=true)] internal static extern bool DuplicateTokenEx(IntPtr token, uint access, IntPtr attributes, int impersonation, int kind, out IntPtr copy);
        [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] internal static extern bool LookupPrivilegeValue(string system, string name, out Luid value);
        [DllImport("advapi32.dll", SetLastError=true)] internal static extern bool SaferCreateLevel(uint scope, uint level, uint flags, out IntPtr handle, IntPtr reserved);
        [DllImport("advapi32.dll", SetLastError=true)] internal static extern bool SaferComputeTokenFromLevel(IntPtr level, IntPtr input, out IntPtr output, uint flags, IntPtr reserved);
        [DllImport("advapi32.dll")] internal static extern bool SaferCloseLevel(IntPtr level);
        [DllImport("advapi32.dll", SetLastError=true)] internal static extern bool CreateRestrictedToken(IntPtr token, uint flags, uint disabledCount, ref SidAttributes disabled, uint deletedCount, IntPtr deleted, uint restrictedCount, IntPtr restricted, out IntPtr output);
        [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] internal static extern bool ConvertStringSidToSid(string text, out IntPtr sid);
        [DllImport("advapi32.dll")] internal static extern uint GetLengthSid(IntPtr sid);
        [DllImport("kernel32.dll")] internal static extern IntPtr LocalFree(IntPtr value);
        [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] internal static extern bool CreateProcessWithTokenW(IntPtr token, uint logonFlags, string application, StringBuilder command, uint flags, IntPtr environment, string cwd, ref StartupInfo startup, out ProcessInfo info);
        [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] internal static extern bool CreateProcessAsUserW(IntPtr token, string application, StringBuilder command, IntPtr processAttributes, IntPtr threadAttributes, bool inherit, uint flags, IntPtr environment, string cwd, ref StartupInfo startup, out ProcessInfo info);
    }

    public static class FilteredProcess {
        const uint Query = 8, Duplicate = 2, Assign = 1, AdjustDefault = 128;
        public static LaunchDiagnostics LastLaunchDiagnostics;

        static IntPtr Information(IntPtr token, int kind) {
            uint size;
            Native.GetTokenInformation(token, kind, IntPtr.Zero, 0, out size);
            if (size == 0) throw new Win32Exception();
            IntPtr data = Marshal.AllocHGlobal(checked((int)size));
            if (!Native.GetTokenInformation(token, kind, data, size, out size)) {
                int error = Marshal.GetLastWin32Error(); Marshal.FreeHGlobal(data); throw new Win32Exception(error);
            }
            return data;
        }
        static int Number(IntPtr token, int kind) {
            IntPtr data = Information(token, kind);
            try { return Marshal.ReadInt32(data); } finally { Marshal.FreeHGlobal(data); }
        }
        static TokenInfo Inspect(IntPtr token) {
            TokenInfo result = new TokenInfo();
            result.IsElevated = Number(token, 20) != 0;
            result.ElevationType = Number(token, 18);
            IntPtr data = Information(token, 1);
            try { result.UserSid = new SecurityIdentifier(Marshal.ReadIntPtr(data)).Value; }
            finally { Marshal.FreeHGlobal(data); }
            data = Information(token, 25);
            try { result.IntegritySid = new SecurityIdentifier(Marshal.ReadIntPtr(data)).Value; }
            finally { Marshal.FreeHGlobal(data); }
            string[] components = result.IntegritySid.Split('-');
            result.IntegrityRid = UInt32.Parse(components[components.Length - 1]);
            data = Information(token, 2);
            try {
                int count = Marshal.ReadInt32(data);
                int offset = Marshal.OffsetOf(typeof(Native.Groups), "First").ToInt32();
                int stride = Marshal.SizeOf(typeof(Native.SidAttributes));
                for (int index = 0; index < count; index++) {
                    Native.SidAttributes group = (Native.SidAttributes)Marshal.PtrToStructure(IntPtr.Add(data, offset + index * stride), typeof(Native.SidAttributes));
                    if (new SecurityIdentifier(group.Sid).Value == "S-1-5-32-544")
                        result.AdministratorsEnabled = (group.Attributes & 4) != 0 && (group.Attributes & 16) == 0;
                }
            } finally { Marshal.FreeHGlobal(data); }
            return result;
        }
        public static TokenInfo InspectCurrent() {
            IntPtr token;
            if (!Native.OpenProcessToken(Native.GetCurrentProcess(), Query, out token)) throw new Win32Exception();
            try { return Inspect(token); } finally { Native.CloseHandle(token); }
        }
        static void Validate(TokenInfo info, string user) {
            if (info.UserSid != user || info.IsElevated || info.AdministratorsEnabled || info.IntegrityRid < 8192 || info.IntegrityRid >= 12288)
                throw new InvalidOperationException("Refusing non-filtered token: sameUser=" + (info.UserSid == user) + ", integrity=" + info.IntegritySid + ", elevated=" + info.IsElevated + ", adminEnabled=" + info.AdministratorsEnabled);
        }
        static void Medium(IntPtr token) {
            if (Inspect(token).IntegrityRid < 12288) return;
            IntPtr sid;
            if (!Native.ConvertStringSidToSid("S-1-16-8192", out sid)) throw new Win32Exception();
            try {
                Native.SidAttributes label = new Native.SidAttributes { Sid = sid, Attributes = 32 };
                if (!Native.SetTokenInformation(token, 25, ref label, (uint)Marshal.SizeOf(typeof(Native.SidAttributes)) + Native.GetLengthSid(sid))) throw new Win32Exception();
            } finally { Native.LocalFree(sid); }
        }
        static IntPtr Candidate(IntPtr original, int method) {
            IntPtr token = IntPtr.Zero;
            if (method == 0) {
                IntPtr data = Information(original, 19);
                try { token = Marshal.ReadIntPtr(data); } finally { Marshal.FreeHGlobal(data); }
            } else if (method == 1) {
                IntPtr level;
                if (!Native.SaferCreateLevel(1, 0x20000, 1, out level, IntPtr.Zero)) throw new Win32Exception();
                try {
                    // No MAKE_INERT/SANDBOX_INERT: retain application-control policy checks.
                    if (!Native.SaferComputeTokenFromLevel(level, original, out token, 0, IntPtr.Zero)) throw new Win32Exception();
                } finally { Native.SaferCloseLevel(level); }
            } else {
                IntPtr admin;
                if (!Native.ConvertStringSidToSid("S-1-5-32-544", out admin)) throw new Win32Exception();
                try {
                    Native.SidAttributes disabled = new Native.SidAttributes { Sid = admin };
                    // Disable privileges + LUA_TOKEN, and make Administrators deny-only.
                    if (!Native.CreateRestrictedToken(original, 1 | 4, 1, ref disabled, 0, IntPtr.Zero, 0, IntPtr.Zero, out token)) throw new Win32Exception();
                } finally { Native.LocalFree(admin); }
            }
            if (token == IntPtr.Zero) throw new InvalidOperationException("Token filtering returned no token.");
            try {
                IntPtr primary;
                if (!Native.DuplicateTokenEx(token, Query | Duplicate | Assign | AdjustDefault, IntPtr.Zero, 2, 1, out primary)) throw new Win32Exception();
                return primary;
            } finally { Native.CloseHandle(token); }
        }
        static IntPtr EnvironmentBlock() {
            List<string> entries = new List<string>();
            foreach (DictionaryEntry item in Environment.GetEnvironmentVariables()) entries.Add(item.Key + "=" + item.Value);
            entries.Sort(StringComparer.OrdinalIgnoreCase);
            return Marshal.StringToHGlobalUni(String.Join("\0", entries.ToArray()) + "\0\0");
        }
        static Dictionary<string, string> Privileges(IntPtr token) {
            Dictionary<string, string> result = new Dictionary<string, string>();
            IntPtr data = Information(token, 3);
            try {
                int count = Marshal.ReadInt32(data);
                int stride = Marshal.SizeOf(typeof(Native.LuidAttributes));
                foreach (string name in new[] { "SeImpersonatePrivilege", "SeIncreaseQuotaPrivilege", "SeAssignPrimaryTokenPrivilege" }) {
                    Native.Luid wanted;
                    if (!Native.LookupPrivilegeValue(null, name, out wanted)) throw new Win32Exception();
                    string state = "absent";
                    for (int index = 0; index < count; index++) {
                        Native.LuidAttributes entry = (Native.LuidAttributes)Marshal.PtrToStructure(IntPtr.Add(data, 4 + index * stride), typeof(Native.LuidAttributes));
                        if (entry.Value.Low == wanted.Low && entry.Value.High == wanted.High) {
                            state = (entry.Attributes & 2) != 0 ? "present-enabled" : "present-disabled";
                            break;
                        }
                    }
                    result.Add(name, state);
                }
            } finally { Marshal.FreeHGlobal(data); }
            return result;
        }
        public static LaunchedProcess LaunchFiltered(string executable, string commandLine, string workingDirectory) {
            LastLaunchDiagnostics = null;
            if (!Path.IsPathRooted(executable) || !File.Exists(executable) || !Directory.Exists(workingDirectory))
                throw new ArgumentException("Expected an existing absolute executable and working directory.");
            IntPtr original;
            if (!Native.OpenProcessToken(Native.GetCurrentProcess(), Query | Duplicate, out original)) throw new Win32Exception();
            IntPtr selected = IntPtr.Zero;
            string source = null;
            List<string> failures = new List<string>();
            string[] methods = { "linked-token", "safer-normal-user", "restricted-lua-token" };
            try {
                string user = Inspect(original).UserSid;
                for (int index = 0; index < methods.Length; index++) {
                    try {
                        selected = Candidate(original, index);
                        Medium(selected);
                        Validate(Inspect(selected), user);
                        source = methods[index]; break;
                    } catch (Exception error) {
                        failures.Add(methods[index] + ": " + error.Message);
                        if (selected != IntPtr.Zero) { Native.CloseHandle(selected); selected = IntPtr.Zero; }
                    }
                }
                if (selected == IntPtr.Zero) throw new InvalidOperationException("No verified filtered token. " + String.Join("; ", failures.ToArray()));
                IntPtr environment = EnvironmentBlock();
                Native.ProcessInfo process = new Native.ProcessInfo();
                try {
                    Native.StartupInfo startup = new Native.StartupInfo();
                    startup.cb = (uint)Marshal.SizeOf(typeof(Native.StartupInfo));
                    // NULL desktop inherits the actual interactive station and its same-user ACL.
                    bool started = Native.CreateProcessWithTokenW(selected, 0, executable, new StringBuilder(commandLine), 0x400 | 4, environment, workingDirectory, ref startup, out process);
                    int launchError = started ? 0 : Marshal.GetLastWin32Error();
                    TokenInfo filtered = Inspect(selected);
                    LaunchDiagnostics diagnostics = new LaunchDiagnostics {
                        Source = source, WithTokenError = launchError,
                        WithTokenMessage = launchError == 0 ? "success" : new Win32Exception(launchError).Message,
                        FilteredIntegritySid = filtered.IntegritySid,
                        FilteredIsElevated = filtered.IsElevated,
                        FilteredAdministratorsEnabled = filtered.AdministratorsEnabled
                    };
                    LastLaunchDiagnostics = diagnostics;
                    try { diagnostics.BootstrapPrivileges = Privileges(original); }
                    catch (Exception error) {
                        diagnostics.BootstrapPrivileges = new Dictionary<string, string> { { "inspection-error", error.Message } };
                    }
                    if (!started && launchError == 1314) {
                        started = Native.CreateProcessAsUserW(selected, executable, new StringBuilder(commandLine), IntPtr.Zero, IntPtr.Zero, false, 0x400 | 4, environment, workingDirectory, ref startup, out process);
                        if (!started) launchError = Marshal.GetLastWin32Error();
                        else source += "/CreateProcessAsUser";
                        diagnostics.AsUserError = started ? 0 : launchError;
                        diagnostics.AsUserMessage = started ? "success" : new Win32Exception(launchError).Message;
                    }
                    if (!started) throw new Win32Exception(launchError, "Filtered worker launch failed: source=" + source + "; CreateProcessWithTokenW=" + diagnostics.WithTokenError + " (" + diagnostics.WithTokenMessage + "); CreateProcessAsUserW=" + (diagnostics.AsUserError.HasValue ? diagnostics.AsUserError.Value.ToString() + " (" + diagnostics.AsUserMessage + ")" : "not attempted"));
                    IntPtr childToken;
                    if (!Native.OpenProcessToken(process.Process, Query, out childToken)) throw new Win32Exception();
                    TokenInfo child;
                    try { child = Inspect(childToken); Validate(child, user); } finally { Native.CloseHandle(childToken); }
                    if (Native.ResumeThread(process.Thread) == UInt32.MaxValue) throw new Win32Exception();
                    LaunchedProcess result = new LaunchedProcess { Handle = process.Process, ProcessId = process.ProcessId, Source = source, Token = child };
                    process.Process = IntPtr.Zero;
                    return result;
                } finally {
                    Marshal.FreeHGlobal(environment);
                    if (process.Thread != IntPtr.Zero) Native.CloseHandle(process.Thread);
                    if (process.Process != IntPtr.Zero) { Native.TerminateProcess(process.Process, 1); Native.CloseHandle(process.Process); }
                }
            } finally {
                if (selected != IntPtr.Zero) Native.CloseHandle(selected);
                Native.CloseHandle(original);
            }
        }
    }
}
