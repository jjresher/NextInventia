import { Scale } from "lucide-react";

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-primary-100/60 bg-white/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-500 to-accent-600 flex items-center justify-center">
              <Scale className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-semibold gradient-text">Patentologos</span>
          </div>
          <p className="text-sm text-gray-400">
            &copy; {new Date().getFullYear()} Patentologos &mdash; Buscador inteligente de patentes
          </p>
        </div>
      </div>
    </footer>
  );
}
