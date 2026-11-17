import { type FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  CheckCircle2,
  Cloud,
  KeyRound,
  Laptop,
  Loader2,
  LogOut,
  Moon,
  Palette,
  Plus,
  RefreshCw,
  Shield,
  ShieldAlert,
  Sun,
  Trash2,
  User as UserIcon,
  Wrench,
} from "lucide-react";
import {
  connectAwsAccount,
  disconnectAwsAccount,
  updateAwsAccount,
  verifyAwsAccount,
} from "@/api/awsAccounts";
import type { AWSAccount } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/shared/PageHeader";
import { QueryState } from "@/components/shared/QueryState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { queryKeys } from "@/hooks/queryKeys";
import { useAwsAccounts } from "@/hooks/useApiQueries";
import { useNotificationPreferences } from "@/lib/preferences";
import { type ThemePreference, useTheme } from "@/lib/theme";
import { cn, formatDate } from "@/lib/utils";

function extractErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Request failed";
}

export const AWS_REGIONS = [
  "us-east-1",
  "us-east-2",
  "us-west-1",
  "us-west-2",
  "ca-central-1",
  "eu-west-1",
  "eu-west-2",
  "eu-central-1",
  "ap-south-1",
  "ap-southeast-1",
  "ap-southeast-2",
  "ap-northeast-1",
] as const;

type SettingsTab = "aws" | "profile" | "appearance" | "notifications" | "security";

const TABS: { id: SettingsTab; label: string; icon: typeof Cloud }[] = [
  { id: "aws", label: "AWS Accounts", icon: Cloud },
  { id: "profile", label: "Profile", icon: UserIcon },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "security", label: "Security", icon: Shield },
];

function isValidTab(value: string | null): value is SettingsTab {
  return (
    value === "aws" ||
    value === "profile" ||
    value === "appearance" ||
    value === "notifications" ||
    value === "security"
  );
}

function verificationBadgeVariant(status: AWSAccount["verification_status"]) {
  switch (status) {
    case "verified":
      return "success" as const;
    case "expired":
      return "warning" as const;
    case "invalid":
      return "destructive" as const;
    default:
      return "secondary" as const;
  }
}

export default function SettingsPage() {
  const { user, isSimulationMode } = useAuth();
  const isGuestSimulation = isSimulationMode && !user;
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const activeTab: SettingsTab = isValidTab(tabParam)
    ? tabParam
    : isGuestSimulation
      ? "appearance"
      : "aws";

  const setActiveTab = (tab: SettingsTab) => {
    setSearchParams({ tab }, { replace: true });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Manage connected AWS accounts, user profile, theme appearance, notification preferences, and account security"
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-3">
        {TABS.map(({ id, label, icon: Icon }) => (
          <Button
            key={id}
            type="button"
            variant={activeTab === id ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab(id)}
            className="gap-2"
          >
            <Icon className="h-4 w-4" />
            {label}
          </Button>
        ))}
      </div>

      {activeTab === "aws" &&
        (isGuestSimulation ? (
          <SimulationAccountGate
            title="AWS Account Connections Require a Personal Workspace"
            description="Simulation Mode runs strictly against isolated synthetic demo data and never connects to live AWS accounts. Sign in or create a personal account to connect IAM or AWS Academy Learner Lab credentials."
          />
        ) : (
          <AwsAccountsSection />
        ))}
      {activeTab === "profile" &&
        (isGuestSimulation ? (
          <SimulationAccountGate
            title="User Profile Unavailable in Simulation Mode"
            description="You are currently exploring Autonomous FinOps Guardian as a Simulation Guest. Sign in or create an account to manage your personal profile."
          />
        ) : (
          <ProfileSection />
        ))}
      {activeTab === "appearance" && <AppearanceSection />}
      {activeTab === "notifications" && <NotificationsSection />}
      {activeTab === "security" &&
        (isGuestSimulation ? (
          <SimulationAccountGate
            title="Account Security Requires Authentication"
            description="Password management and multi-device session revocation apply to personal accounts. Sign in or create an account to configure security settings."
          />
        ) : (
          <SecuritySection />
        ))}
    </div>
  );
}

function SimulationAccountGate({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const { exitSimulationMode } = useAuth();
  const navigate = useNavigate();

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        <Button
          type="button"
          onClick={() => {
            exitSimulationMode();
            navigate("/login");
          }}
        >
          Sign In to Personal Workspace
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            exitSimulationMode();
            navigate("/register");
          }}
        >
          Create Personal Account
        </Button>
      </CardContent>
    </Card>
  );
}

function AwsAccountsSection() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: accounts, isLoading, isError, error, refetch } = useAwsAccounts();

  // Connect form state
  const [displayName, setDisplayName] = useState("");
  const [defaultRegion, setDefaultRegion] = useState<string>("us-east-1");
  const [accessKeyId, setAccessKeyId] = useState("");
  const [secretAccessKey, setSecretAccessKey] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [verifyNow, setVerifyNow] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  // Per-account action state
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingAccount, setEditingAccount] = useState<AWSAccount | null>(null);
  const [editDisplayName, setEditDisplayName] = useState("");
  const [editRegion, setEditRegion] = useState("us-east-1");
  const [editAccessKeyId, setEditAccessKeyId] = useState("");
  const [editSecretAccessKey, setEditSecretAccessKey] = useState("");
  const [editSessionToken, setEditSessionToken] = useState("");
  const [clearSessionToken, setClearSessionToken] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const invalidateAccounts = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.awsAccounts });
  };

  const handleConnect = async (event: FormEvent) => {
    event.preventDefault();
    setConnectError(null);
    setConnecting(true);

    const payload = {
      display_name: displayName.trim(),
      default_region: defaultRegion,
      access_key_id: accessKeyId.trim(),
      secret_access_key: secretAccessKey.trim(),
      session_token: sessionToken.trim() ? sessionToken.trim() : null,
      verify: verifyNow,
    };

    // Immediately clear sensitive inputs from component state after constructing request payload
    setAccessKeyId("");
    setSecretAccessKey("");
    setSessionToken("");

    try {
      const created = await connectAwsAccount(payload);
      setDisplayName("");
      await invalidateAccounts();
      toast.success(
        "AWS account connected",
        created.aws_account_id
          ? `${created.display_name} (${created.aws_account_id}) verified in ${created.default_region}.`
          : `${created.display_name} saved in ${created.default_region}.`
      );
    } catch (err) {
      const msg = extractErrorMessage(err);
      setConnectError(msg);
      toast.error("Failed to connect AWS account", msg);
    } finally {
      setConnecting(false);
    }
  };

  const handleVerify = async (account: AWSAccount) => {
    setVerifyingId(account.id);
    try {
      const updated = await verifyAwsAccount(account.id);
      await invalidateAccounts();
      if (updated.verification_status === "verified") {
        toast.success(
          "Credentials verified",
          `${updated.display_name} verified against AWS STS (${updated.aws_account_id ?? "account"}).`
        );
      } else {
        toast.error(
          `Verification ${updated.verification_status}`,
          "Credentials could not be verified with AWS STS."
        );
      }
    } catch (err) {
      toast.error("Verification failed", extractErrorMessage(err));
    } finally {
      setVerifyingId(null);
    }
  };

  const openEdit = (account: AWSAccount) => {
    setEditingAccount(account);
    setEditDisplayName(account.display_name);
    setEditRegion(account.default_region);
    setEditAccessKeyId("");
    setEditSecretAccessKey("");
    setEditSessionToken("");
    setClearSessionToken(false);
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingAccount(null);
    setEditAccessKeyId("");
    setEditSecretAccessKey("");
    setEditSessionToken("");
    setClearSessionToken(false);
    setEditError(null);
  };

  const handleSaveEdit = async (event: FormEvent) => {
    event.preventDefault();
    if (!editingAccount) return;
    setEditError(null);

    const hasKeyUpdate = Boolean(editAccessKeyId.trim() || editSecretAccessKey.trim());
    if (hasKeyUpdate && (!editAccessKeyId.trim() || !editSecretAccessKey.trim())) {
      setEditError("Provide both Access Key ID and Secret Access Key when rotating credentials.");
      return;
    }

    setSavingEdit(true);
    const payload = {
      display_name: editDisplayName.trim(),
      default_region: editRegion,
      ...(hasKeyUpdate
        ? {
            access_key_id: editAccessKeyId.trim(),
            secret_access_key: editSecretAccessKey.trim(),
          }
        : {}),
      ...(editSessionToken.trim() ? { session_token: editSessionToken.trim() } : {}),
      ...(clearSessionToken ? { clear_session_token: true } : {}),
      verify: true,
    };

    // Clear sensitive fields immediately
    setEditAccessKeyId("");
    setEditSecretAccessKey("");
    setEditSessionToken("");

    try {
      const updated = await updateAwsAccount(editingAccount.id, payload);
      await invalidateAccounts();
      setEditingAccount(null);
      toast.success(
        "AWS account updated",
        `${updated.display_name} (${updated.default_region}) saved and verified.`
      );
    } catch (err) {
      const msg = extractErrorMessage(err);
      setEditError(msg);
      toast.error("Update failed", msg);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDisconnect = async (account: AWSAccount) => {
    setDeletingId(account.id);
    try {
      await disconnectAwsAccount(account.id);
      if (editingAccount?.id === account.id) {
        cancelEdit();
      }
      await invalidateAccounts();
      toast.success("AWS account disconnected", `${account.display_name} was removed.`);
    } catch (err) {
      toast.error("Failed to disconnect account", extractErrorMessage(err));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-12">
      <Card className="xl:col-span-5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" />
            Connect AWS Account
          </CardTitle>
          <CardDescription>
            Credentials are encrypted at rest with AES-256-GCM and isolated to your user account.
            Supports both permanent IAM keys and temporary AWS Academy Learner Lab session tokens.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void handleConnect(e)} className="space-y-4">
            {connectError && (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
                {connectError}
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="aws-display-name">
                Display Name
              </label>
              <Input
                id="aws-display-name"
                placeholder="e.g. Production AWS or Learner Lab"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                minLength={2}
                maxLength={120}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Default AWS Region</label>
              <Select value={defaultRegion} onValueChange={setDefaultRegion}>
                <SelectTrigger>
                  <SelectValue placeholder="Select region" />
                </SelectTrigger>
                <SelectContent>
                  {AWS_REGIONS.map((region) => (
                    <SelectItem key={region} value={region}>
                      {region}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="aws-access-key">
                AWS Access Key ID
              </label>
              <Input
                id="aws-access-key"
                placeholder="AKIA... or ASIA..."
                value={accessKeyId}
                onChange={(e) => setAccessKeyId(e.target.value)}
                autoComplete="off"
                required
                minLength={16}
                maxLength={128}
              />
              <p className="text-[11px] text-muted-foreground">
                Starts with <code className="font-mono">AKIA</code> for permanent IAM users or{" "}
                <code className="font-mono">ASIA</code> for temporary STS / Learner Lab credentials.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="aws-secret-key">
                AWS Secret Access Key
              </label>
              <Input
                id="aws-secret-key"
                type="password"
                placeholder="••••••••••••••••••••••••••••••••••••••••"
                value={secretAccessKey}
                onChange={(e) => setSecretAccessKey(e.target.value)}
                autoComplete="new-password"
                required
                minLength={16}
                maxLength={256}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="aws-session-token">
                AWS Session Token <span className="text-muted-foreground/70">(optional — required for Learner Lab / ASIA keys)</span>
              </label>
              <Input
                id="aws-session-token"
                type="password"
                placeholder="Paste temporary AWS_SESSION_TOKEN if using STS / Learner Lab"
                value={sessionToken}
                onChange={(e) => setSessionToken(e.target.value)}
                autoComplete="new-password"
              />
            </div>

            <label className="flex items-center gap-2 text-xs text-foreground">
              <input
                type="checkbox"
                checked={verifyNow}
                onChange={(e) => setVerifyNow(e.target.checked)}
                className="h-4 w-4 rounded border-border accent-primary"
              />
              Verify credentials immediately via AWS STS GetCallerIdentity
            </label>

            <Button type="submit" className="w-full gap-2" disabled={connecting}>
              {connecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              {connecting ? "Connecting & Verifying…" : "Connect AWS Account"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4 xl:col-span-7">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Connected AWS Accounts</CardTitle>
              <CardDescription>
                Select any connected account when launching a Live AWS Scan from the Overview page
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isLoading}>
              <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", isLoading && "animate-spin")} />
              Refresh
            </Button>
          </CardHeader>
          <CardContent>
            <QueryState
              isLoading={isLoading}
              isError={isError}
              error={error}
              onRetry={() => void refetch()}
              isEmpty={!isLoading && (!accounts || accounts.length === 0)}
              loadingMessage="Loading connected AWS accounts..."
              emptyMessage="No AWS accounts connected yet. Use the form on the left to connect an IAM user or AWS Academy Learner Lab session."
            >
              {accounts && accounts.length > 0 && (
                <div className="space-y-3">
                  {accounts.map((account) => {
                    const isEditing = editingAccount?.id === account.id;
                    return (
                      <div
                        key={account.id}
                        className="rounded-lg border border-border bg-background/60 p-4 space-y-3"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-foreground">
                                {account.display_name}
                              </p>
                              <Badge variant={verificationBadgeVariant(account.verification_status)}>
                                {account.verification_status}
                              </Badge>
                              <Badge variant="outline">
                                {account.has_session_token
                                  ? "Temporary (Session Token)"
                                  : "Permanent IAM"}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground font-mono">
                              Key: {account.access_key_id_masked} · Region: {account.default_region}
                              {account.aws_account_id ? ` · Account ID: ${account.aws_account_id}` : ""}
                            </p>
                            {account.arn && (
                              <p className="text-[11px] text-muted-foreground font-mono break-all">
                                ARN: {account.arn}
                              </p>
                            )}
                            {account.last_verified_at && (
                              <p className="text-[11px] text-muted-foreground">
                                Last verified: {formatDate(account.last_verified_at)}
                              </p>
                            )}
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void handleVerify(account)}
                              disabled={verifyingId === account.id}
                            >
                              {verifyingId === account.id ? (
                                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                              )}
                              Verify
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => (isEditing ? cancelEdit() : openEdit(account))}
                            >
                              <Wrench className="mr-1.5 h-3.5 w-3.5" />
                              {isEditing ? "Cancel" : "Update"}
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => void handleDisconnect(account)}
                              disabled={deletingId === account.id}
                            >
                              {deletingId === account.id ? (
                                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                              )}
                              Disconnect
                            </Button>
                          </div>
                        </div>

                        {isEditing && (
                          <form
                            onSubmit={(e) => void handleSaveEdit(e)}
                            className="mt-3 space-y-3 border-t border-border pt-3"
                          >
                            <p className="text-xs font-semibold text-foreground">
                              Update Account / Rotate Credentials
                            </p>
                            {editError && (
                              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-400">
                                {editError}
                              </div>
                            )}
                            <div className="grid gap-3 sm:grid-cols-2">
                              <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Display Name</label>
                                <Input
                                  value={editDisplayName}
                                  onChange={(e) => setEditDisplayName(e.target.value)}
                                  required
                                  minLength={2}
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Default Region</label>
                                <Select value={editRegion} onValueChange={setEditRegion}>
                                  <SelectTrigger>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {AWS_REGIONS.map((region) => (
                                      <SelectItem key={region} value={region}>
                                        {region}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>

                            <div className="grid gap-3 sm:grid-cols-2">
                              <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">
                                  New Access Key ID (leave blank to keep current)
                                </label>
                                <Input
                                  placeholder={account.access_key_id_masked}
                                  value={editAccessKeyId}
                                  onChange={(e) => setEditAccessKeyId(e.target.value)}
                                  autoComplete="off"
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">
                                  New Secret Access Key (leave blank to keep current)
                                </label>
                                <Input
                                  type="password"
                                  placeholder="••••••••••••••••••••"
                                  value={editSecretAccessKey}
                                  onChange={(e) => setEditSecretAccessKey(e.target.value)}
                                  autoComplete="new-password"
                                />
                              </div>
                            </div>

                            <div className="space-y-1">
                              <label className="text-xs text-muted-foreground">
                                New Session Token (optional — for refreshed Learner Lab sessions)
                              </label>
                              <Input
                                type="password"
                                placeholder="Paste updated AWS_SESSION_TOKEN"
                                value={editSessionToken}
                                onChange={(e) => setEditSessionToken(e.target.value)}
                                autoComplete="new-password"
                              />
                            </div>

                            {account.has_session_token && (
                              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                <input
                                  type="checkbox"
                                  checked={clearSessionToken}
                                  onChange={(e) => setClearSessionToken(e.target.checked)}
                                  className="h-4 w-4 rounded border-border accent-primary"
                                />
                                Clear stored session token (switch to permanent IAM key)
                              </label>
                            )}

                            <div className="flex justify-end gap-2">
                              <Button type="button" variant="ghost" size="sm" onClick={cancelEdit}>
                                Cancel
                              </Button>
                              <Button type="submit" size="sm" disabled={savingEdit}>
                                {savingEdit && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                                Save & Verify
                              </Button>
                            </div>
                          </form>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </QueryState>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ProfileSection() {
  const { user, updateProfile } = useAuth();
  const toast = useToast();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [username, setUsername] = useState(user?.username ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name);
      setUsername(user.username);
      setEmail(user.email);
    }
  }, [user]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await updateProfile({
        full_name: fullName.trim(),
        username: username.trim(),
        email: email.trim(),
      });
      toast.success("Profile updated", "Your account profile details have been saved.");
    } catch (err) {
      const msg = extractErrorMessage(err);
      setError(msg);
      toast.error("Failed to update profile", msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>User Profile</CardTitle>
        <CardDescription>
          View and update your FinOps Guardian account identity
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {error && (
            <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
              {error}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Account ID</label>
              <Input value={user?.id ?? ""} disabled readOnly className="font-mono text-xs" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Member Since</label>
              <Input
                value={user?.created_at ? formatDate(user.created_at) : "—"}
                disabled
                readOnly
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="profile-fullname">
              Full Name
            </label>
            <Input
              id="profile-fullname"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              minLength={2}
              maxLength={255}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="profile-username">
                Username
              </label>
              <Input
                id="profile-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
                maxLength={120}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="profile-email">
                Email Address
              </label>
              <Input
                id="profile-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Profile Changes
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function AppearanceSection() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const toast = useToast();

  const options: {
    mode: ThemePreference;
    label: string;
    description: string;
    icon: typeof Sun;
  }[] = [
    {
      mode: "light",
      label: "Light",
      description: "Clean high-contrast light palette for bright environments",
      icon: Sun,
    },
    {
      mode: "dark",
      label: "Dark",
      description: "Deep slate FinOps command center palette for low-glare monitoring",
      icon: Moon,
    },
    {
      mode: "system",
      label: "System",
      description: "Automatically match your operating system appearance setting",
      icon: Laptop,
    },
  ];

  const handleSelect = (mode: ThemePreference) => {
    setTheme(mode);
    toast.info("Appearance updated", `Theme preference set to ${mode}.`);
  };

  return (
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>Appearance & Theme</CardTitle>
        <CardDescription>
          Choose how Autonomous FinOps Guardian looks across your sessions. Active theme:{" "}
          <span className="font-semibold text-foreground capitalize">{resolvedTheme}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        {options.map(({ mode, label, description, icon: Icon }) => {
          const selected = theme === mode;
          return (
            <button
              key={mode}
              type="button"
              onClick={() => handleSelect(mode)}
              className={cn(
                "flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-all",
                selected
                  ? "border-primary bg-primary/10 ring-2 ring-primary/30"
                  : "border-border bg-background hover:bg-secondary/60"
              )}
            >
              <div className="flex w-full items-center justify-between">
                <Icon className={cn("h-5 w-5", selected ? "text-primary" : "text-muted-foreground")} />
                {selected && <Badge variant="default">Active</Badge>}
              </div>
              <p className="text-sm font-semibold text-foreground">{label}</p>
              <p className="text-xs text-muted-foreground">{description}</p>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}

function NotificationsSection() {
  const { user } = useAuth();
  const toast = useToast();
  const { preferences, updatePreference } = useNotificationPreferences(user?.id);

  const toggle = (key: keyof typeof preferences, label: string) => {
    const nextValue = !preferences[key];
    updatePreference(key, nextValue);
    toast.info(
      "Notification preference saved",
      `${label} alerts ${nextValue ? "enabled" : "disabled"}.`
    );
  };

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Notification Preferences</CardTitle>
        <CardDescription>
          Control in-app dashboard alerts for pipeline events and anomaly detection. Preferences are
          stored locally for your account in this browser; external email/webhook delivery is not
          enabled on this backend.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-border p-4">
          <div className="space-y-0.5 pr-4">
            <p className="text-sm font-medium text-foreground">Scan Completion Alerts</p>
            <p className="text-xs text-muted-foreground">
              Show an in-app toast notification when a synthetic or live AWS scan finishes
            </p>
          </div>
          <Button
            type="button"
            variant={preferences.scanCompleted ? "default" : "outline"}
            size="sm"
            onClick={() => toggle("scanCompleted", "Scan completion")}
          >
            {preferences.scanCompleted ? "Enabled" : "Disabled"}
          </Button>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-border p-4">
          <div className="space-y-0.5 pr-4">
            <p className="text-sm font-medium text-foreground">Scan Failure Alerts</p>
            <p className="text-xs text-muted-foreground">
              Show an in-app alert if any stage of the eight-stage FinOps pipeline fails
            </p>
          </div>
          <Button
            type="button"
            variant={preferences.scanFailed ? "default" : "outline"}
            size="sm"
            onClick={() => toggle("scanFailed", "Scan failure")}
          >
            {preferences.scanFailed ? "Enabled" : "Disabled"}
          </Button>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-border p-4">
          <div className="space-y-0.5 pr-4">
            <p className="text-sm font-medium text-foreground">Anomaly Detection Highlights</p>
            <p className="text-xs text-muted-foreground">
              Highlight active Isolation Forest anomaly counts when viewing Anomaly Detection
            </p>
          </div>
          <Button
            type="button"
            variant={preferences.anomalyAlerts ? "default" : "outline"}
            size="sm"
            onClick={() => toggle("anomalyAlerts", "Anomaly detection")}
          >
            {preferences.anomalyAlerts ? "Enabled" : "Disabled"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function SecuritySection() {
  const { changePassword, logoutAll } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  const handlePasswordSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setPasswordError(null);

    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }

    setChangingPassword(true);
    const curr = currentPassword;
    const next = newPassword;
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");

    try {
      await changePassword(curr, next);
      toast.success(
        "Password changed",
        "All existing sessions have been revoked. Please sign in with your new password."
      );
      navigate("/login", { replace: true });
    } catch (err) {
      const msg = extractErrorMessage(err);
      setPasswordError(msg);
      toast.error("Password change failed", msg);
    } finally {
      setChangingPassword(false);
    }
  };

  const handleLogoutAll = async () => {
    setLoggingOutAll(true);
    try {
      await logoutAll();
      toast.success("Signed out everywhere", "All active sessions for your account were revoked.");
      navigate("/login", { replace: true });
    } catch (err) {
      toast.error("Failed to revoke sessions", extractErrorMessage(err));
    } finally {
      setLoggingOutAll(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
          <CardDescription>
            Updating your password immediately revokes all active browser sessions and requires
            signing in again.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void handlePasswordSubmit(e)} className="space-y-4">
            {passwordError && (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
                {passwordError}
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="sec-curr-pwd">
                Current Password
              </label>
              <Input
                id="sec-curr-pwd"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                required
                minLength={8}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="sec-new-pwd">
                New Password (minimum 12 characters)
              </label>
              <Input
                id="sec-new-pwd"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="sec-confirm-pwd">
                Confirm New Password
              </label>
              <Input
                id="sec-confirm-pwd"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
              />
            </div>

            <Button type="submit" disabled={changingPassword} className="w-full">
              {changingPassword && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Update Password
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-amber-400" />
            Active Session Control
          </CardTitle>
          <CardDescription>
            Immediately revoke all active refresh and access sessions across every device and
            browser signed into your account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-border bg-background/60 p-4 text-xs text-muted-foreground space-y-1">
            <p className="font-medium text-foreground">When to use Sign Out All Sessions:</p>
            <p>
              Use this if you signed in on a shared workstation, rotated credentials, or suspect an
              unauthorized session. Your current browser will also be signed out immediately.
            </p>
          </div>
          <Button
            type="button"
            variant="destructive"
            onClick={() => void handleLogoutAll()}
            disabled={loggingOutAll}
            className="gap-2"
          >
            {loggingOutAll ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LogOut className="h-4 w-4" />
            )}
            Sign Out All Sessions
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
