import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "group/badge inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1.5 overflow-hidden rounded-full border border-transparent px-2.5 py-0.5 text-xs font-medium whitespace-nowrap transition-all duration-200 select-none [&>svg]:pointer-events-none [&>svg]:size-3.5",
  {
    variants: {
      variant: {
        default: "bg-[#8B5CF6]/15 text-[#A78BFA] border-[#8B5CF6]/30",
        secondary: "bg-[#22D3EE]/15 text-[#22D3EE] border-[#22D3EE]/30",
        tertiary: "bg-[#F472B6]/15 text-[#F472B6] border-[#F472B6]/30",
        success: "bg-[#34D399]/15 text-[#34D399] border-[#34D399]/30",
        warning: "bg-[#FBBF24]/15 text-[#FBBF24] border-[#FBBF24]/30",
        destructive: "bg-[#F87171]/15 text-[#F87171] border-[#F87171]/30",
        outline: "border-white/10 text-zinc-300 bg-white/[0.04]",
        chip: "bg-[#1E1E2A] text-[#A1A1AA] border-[#27272A] hover:bg-[#27272A] hover:text-[#F4F4F5]",
        chipSelected: "bg-[#8B5CF6] text-white border-[#8B5CF6] shadow-[0_0_12px_rgba(139,92,246,0.4)]",
        ghost: "bg-transparent text-muted-foreground hover:text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
