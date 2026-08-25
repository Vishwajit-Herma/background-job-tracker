import { redirect } from "next/navigation";

// API Keys have been moved into the Projects page.
// Redirect any direct visits to /api-keys → /projects
export default function APIKeysRedirectPage() {
  redirect("/projects");
}
