"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/use-auth";
import { updateUser } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Lock, CheckCircle2, ExternalLink } from "lucide-react";
import { UserAvatar } from "@/components/bjt/user-avatar";
import { ApiError } from "@/lib/api/client";

export default function SettingsPage() {
  const { user } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setFirstName(user.first_name || "");
      setLastName(user.last_name || "");
      setEmail(user.email || "");
    }
  }, [user]);

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsUpdating(true);
    setSuccessMsg(null);
    setErrorMsg(null);

    try {
      await updateUser({
        first_name: firstName,
        last_name: lastName,
      });
      setSuccessMsg("Profile updated successfully");
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e) {
      const err = e as ApiError;
      if (err.errors) {
        // Just extract the first error message
        const firstErrorKey = Object.keys(err.errors)[0];
        const firstError = err.errors[firstErrorKey];
        setErrorMsg(Array.isArray(firstError) ? firstError[0] : String(firstError));
      } else {
        setErrorMsg("Failed to update profile");
      }
    } finally {
      setIsUpdating(false);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>
              Update your personal information.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleUpdateProfile}>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-4 mb-6">
                <UserAvatar user={user} size="xl" />
                <div className="space-y-1">
                  <p className="text-sm font-medium leading-none">Avatar</p>
                  <p className="text-xs text-muted-foreground">
                    Profile pictures are provided automatically via Gravatar linked to {user.email}.
                  </p>
                  <a
                    href="https://gravatar.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium pt-1"
                  >
                    Change avatar on Gravatar.com <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">First Name</Label>
                  <Input 
                    id="firstName" 
                    value={firstName} 
                    onChange={(e) => setFirstName(e.target.value)} 
                    disabled={isUpdating}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input 
                    id="lastName" 
                    value={lastName} 
                    onChange={(e) => setLastName(e.target.value)} 
                    disabled={isUpdating}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="email">Email Address</Label>
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground font-normal">
                    <Lock className="h-3 w-3" /> Locked
                  </span>
                </div>
                <Input 
                  id="email" 
                  type="email"
                  value={email} 
                  disabled
                  className="bg-muted/50 cursor-not-allowed text-muted-foreground"
                />
                <p className="text-xs text-muted-foreground">
                  Email address is linked to your account authentication and cannot be edited directly.
                </p>
              </div>

              {errorMsg && (
                <div className="text-sm text-destructive font-medium">{errorMsg}</div>
              )}
              {successMsg && (
                <div className="flex items-center gap-2 text-sm text-green-600 font-medium">
                  <CheckCircle2 className="h-4 w-4" />
                  {successMsg}
                </div>
              )}
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={isUpdating}>
                {isUpdating ? "Saving..." : "Save Changes"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
