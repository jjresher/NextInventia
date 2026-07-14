import { Scale, Search, Database, Zap } from "lucide-react";

export default function AcercaPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-12 animate-fade-in">
      <section className="text-center space-y-4 py-8">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary-500 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-500/25">
          <Scale className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-4xl font-extrabold gradient-text">Patentologos</h1>
        <p className="text-gray-500 text-lg max-w-lg mx-auto leading-relaxed">
          Plataforma de búsqueda y análisis de patentes, diseñada para facilitar
          la exploración de propiedad intelectual.
        </p>
      </section>

      <div className="grid sm:grid-cols-3 gap-6">
        <FeatureCard
          icon={Search}
          title="Búsqueda rápida"
          description="Encuentra patentes por título, abstract o número de publicación al instante."
        />
        <FeatureCard
          icon={Database}
          title="Base completa"
          description="Accede a miles de patentes indexadas con información detallada y clasificaciones."
        />
        <FeatureCard
          icon={Zap}
          title="Interfaz moderna"
          description="Experiencia de usuario optimizada con diseño limpio y navegación intuitiva."
        />
      </div>

      <section className="bg-white/80 backdrop-blur-sm rounded-2xl border border-gray-100 p-8 space-y-4">
        <h2 className="text-xl font-bold text-gray-900">Sobre el proyecto</h2>
        <p className="text-gray-600 leading-relaxed">
          Patentologos es un proyecto académico desarrollado para explorar y
          visualizar información de patentes. La plataforma permite buscar,
          filtrar y analizar patentes de manera eficiente, brindando acceso a
          datos como clasificaciones CPC/IPC, resúmenes, descripciones y
          reivindicaciones.
        </p>
        <p className="text-gray-600 leading-relaxed">
          Construido con tecnologías modernas como Next.js, Tailwind CSS y una
          API REST como backend.
        </p>
      </section>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-gray-100 p-6 space-y-3 hover:shadow-lg hover:shadow-primary-500/5 hover:border-primary-200 transition-all duration-300">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center text-primary-500">
        <Icon className="w-5 h-5" />
      </div>
      <h3 className="font-semibold text-gray-900">{title}</h3>
      <p className="text-sm text-gray-500 leading-relaxed">{description}</p>
    </div>
  );
}
