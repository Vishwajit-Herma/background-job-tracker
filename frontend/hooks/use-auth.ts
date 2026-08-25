import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCurrentUser, login, logout, register, verifyEmail, resetPassword, resetPasswordConfirm } from "@/lib/api/auth";
import { useRouter } from "next/navigation";

export function useAuth() {
  const queryClient = useQueryClient();
  const router = useRouter();

  const userQuery = useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: async () => {
      const user = await getCurrentUser();
      queryClient.setQueryData(["current-user"], user);
      router.push("/projects");
    },
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(["current-user"], null);
      queryClient.clear();
      router.push("/login");
    },
  });

  const registerMutation = useMutation({
    mutationFn: register,
  });

  const verifyEmailMutation = useMutation({
    mutationFn: verifyEmail,
  });

  const resetPasswordMutation = useMutation({
    mutationFn: resetPassword,
  });

  const resetPasswordConfirmMutation = useMutation({
    mutationFn: resetPasswordConfirm,
  });

  return {
    user: userQuery.data,
    isLoading: userQuery.isLoading,
    isError: userQuery.isError,
    login: loginMutation.mutateAsync,
    logout: logoutMutation.mutateAsync,
    register: registerMutation.mutateAsync,
    verifyEmail: verifyEmailMutation.mutateAsync,
    resetPassword: resetPasswordMutation.mutateAsync,
    resetPasswordConfirm: resetPasswordConfirmMutation.mutateAsync,
    
    isLoggingIn: loginMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
    isRegistering: registerMutation.isPending,
    
    loginError: loginMutation.error,
    registerError: registerMutation.error,
  };
}
