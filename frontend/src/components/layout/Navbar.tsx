import { Bell, Menu, Search, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";

interface NavbarProps {
  onMenuClick?: () => void;
  title?: string;
}

export function Navbar({ onMenuClick, title = "Dashboard" }: NavbarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card/50 px-4 backdrop-blur-sm lg:px-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick}>
          <Menu className="h-5 w-5" />
        </Button>
        <div>
          <p className="text-sm font-medium text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground">ap-southeast-2 · Last sync 2m ago</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 md:flex">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search resources..."
            className="w-48 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded border border-border px-1.5 text-[10px] text-muted-foreground">⌘K</kbd>
        </div>
        <Button variant="ghost" size="icon">
          <Bell className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon">
          <Settings className="h-4 w-4" />
        </Button>
        <div className="ml-1 flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
          PG
        </div>
      </div>
    </header>
  );
}
