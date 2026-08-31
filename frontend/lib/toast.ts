import { toast } from "@/components/ui/toast";

export function getErrorMessage(err: any, fallback: string): string {
  if (typeof err === "string") return err;
  const resData = err?.response?.data;
  if (!resData) return err?.message || fallback;

  // 1. Check errors object (Keel CustomResponse format: resData.errors)
  if (resData.errors) {
    if (typeof resData.errors === "string") return resData.errors;
    if (typeof resData.errors === "object") {
      if (typeof resData.errors.error === "string") return resData.errors.error;
      if (typeof resData.errors.detail === "string") return resData.errors.detail;
      if (resData.errors.non_field_errors) {
        return Array.isArray(resData.errors.non_field_errors)
          ? resData.errors.non_field_errors.join(", ")
          : String(resData.errors.non_field_errors);
      }
      const values = Object.values(resData.errors);
      if (values.length > 0) {
        const firstVal = values[0];
        if (typeof firstVal === "string") return firstVal;
        if (Array.isArray(firstVal) && firstVal.length > 0) return String(firstVal[0]);
      }
    }
  }

  // 2. Direct error/detail/message keys
  if (resData.error && typeof resData.error === "string") return resData.error;
  if (resData.detail && typeof resData.detail === "string") return resData.detail;
  if (resData.message && resData.message !== "Error" && typeof resData.message === "string") {
    return resData.message;
  }

  return err?.message || fallback;
}

export function toastError(title: string, errOrMessage?: any) {
  const description =
    errOrMessage && typeof errOrMessage !== "string"
      ? getErrorMessage(errOrMessage, title)
      : errOrMessage;
  toast.add({
    title: title || "Error",
    description,
    type: "error",
  });
}

export function toastSuccess(title: string, description?: string) {
  toast.add({
    title,
    description,
    type: "success",
  });
}

export function toastWarning(title: string, description?: string) {
  toast.add({
    title,
    description,
    type: "warning",
  });
}

export function toastInfo(title: string, description?: string) {
  toast.add({
    title,
    description,
    type: "info",
  });
}
