import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"
import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-xl border border-[#3F3F46] bg-[#151520] px-3.5 py-2 text-sm font-sans text-foreground transition-all duration-200 outline-none placeholder:text-zinc-500 hover:border-[#52525B] focus-visible:border-[#8B5CF6] focus-visible:ring-3 focus-visible:ring-[#8B5CF6]/45 disabled:pointer-events-none disabled:cursor-not-allowed disabled:border-[#27272A] disabled:bg-[#0F0F14] disabled:opacity-50 aria-invalid:border-[#F87171] aria-invalid:bg-[#1A1015] aria-invalid:ring-3 aria-invalid:ring-[#F87171]/25 file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export { Input }
