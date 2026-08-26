import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";

interface PaginationProps {
  page: number;
  totalPages: number;
  setPage: (page: number) => void;
  className?: string;
  size?: "sm" | "default";
}

export function PaginationControls({ page, totalPages, setPage, className = "", size = "default" }: PaginationProps) {
  if (totalPages <= 1) return null;

  const btnSize = size === "sm" ? "h-7 w-7 p-0 text-xs" : "h-9 w-9 p-0 text-sm";
  const iconSize = size === "sm" ? "h-3 w-3" : "h-4 w-4";

  // Generate page numbers with ellipsis
  const pages: (number | string)[] = [];
  
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    if (page <= 4) {
      pages.push(1, 2, 3, 4, 5, "...", totalPages);
    } else if (page >= totalPages - 3) {
      pages.push(1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
    } else {
      pages.push(1, "...", page - 1, page, page + 1, "...", totalPages);
    }
  }

  return (
    <div className={`flex items-center justify-between w-full ${className}`}>
      <span className={`text-muted-foreground ${size === "sm" ? "text-xs" : "text-sm"}`}>
        Page {page} of {totalPages}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          className={`${size === "sm" ? "h-7 px-2 text-xs" : ""}`}
          onClick={() => setPage(Math.max(1, page - 1))}
          disabled={page <= 1}
        >
          <ChevronLeft className={`${iconSize} mr-1`} /> Prev
        </Button>
        
        <div className="hidden sm:flex items-center gap-1 mx-1">
          {pages.map((p, i) => (
            p === "..." ? (
              <span key={`ellipsis-${i}`} className="px-1 text-muted-foreground flex items-center justify-center">
                <MoreHorizontal className={iconSize} />
              </span>
            ) : (
              <Button
                key={p}
                variant={page === p ? "default" : "ghost"}
                size="sm"
                className={btnSize}
                onClick={() => setPage(p as number)}
              >
                {p}
              </Button>
            )
          ))}
        </div>

        <Button
          variant="outline"
          size="sm"
          className={`${size === "sm" ? "h-7 px-2 text-xs" : ""}`}
          onClick={() => setPage(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
        >
          Next <ChevronRight className={`${iconSize} ml-1`} />
        </Button>
      </div>
    </div>
  );
}
