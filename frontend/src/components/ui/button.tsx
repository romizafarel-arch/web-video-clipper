import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-xl border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap transition-all duration-200 outline-none select-none focus-visible:ring-3 focus-visible:ring-[#8B5CF6]/50 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-35 disabled:shadow-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-[#8B5CF6] to-[#7C3AED] text-white shadow-[0_0_20px_rgba(139,92,246,0.3)] hover:shadow-[0_0_28px_rgba(139,92,246,0.55)] hover:brightness-110 active:brightness-95",
        secondary:
          "bg-[#22D3EE] text-[#0A0A0F] font-semibold shadow-[0_0_15px_rgba(34,211,238,0.25)] hover:bg-[#22D3EE]/90 hover:shadow-[0_0_24px_rgba(34,211,238,0.45)]",
        outline:
          "border border-white/10 bg-white/[0.04] text-foreground hover:bg-white/[0.08] hover:border-white/20 hover:text-white",
        ghost:
          "border border-[#8B5CF6]/35 bg-transparent text-[#A78BFA] hover:bg-[#8B5CF6]/15 hover:border-[#8B5CF6] hover:text-white",
        destructive:
          "bg-[#EF4444] text-white shadow-[0_0_15px_rgba(239,68,68,0.3)] hover:bg-[#DC2626] hover:shadow-[0_0_24px_rgba(239,68,68,0.5)]",
        link: "text-[#8B5CF6] underline-offset-4 hover:underline hover:text-[#A78BFA]",
      },
      size: {
        default: "h-10 gap-2 px-4 py-2 text-sm",
        sm: "h-8 gap-1.5 px-3 text-xs",
        lg: "h-12 gap-2.5 px-6 text-base font-semibold",
        icon: "size-10 rounded-xl",
        "icon-sm": "size-8 rounded-lg",
        "icon-xs": "size-6 rounded-md",
        "icon-lg": "size-12 rounded-xl",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
