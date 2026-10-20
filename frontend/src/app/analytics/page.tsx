"use client";

import { Database, FlaskConical, GitBranch, LineChart, Rocket, Workflow } from "lucide-react";
import { ServiceTile, type PlatformService } from "@/components/analytics/ServiceTile";

const SERVICES: PlatformService[] = [
  {
    id: "gitea",
    name: "Gitea",
    description: "Исходный код репозиториев mlops",
    url: "https://git.alexshishin.ru/mlops",
    icon: GitBranch,
    accent: "bg-emerald-100 text-emerald-600",
  },
  {
    id: "argocd",
    name: "ArgoCD",
    description: "Статус деплоев и синхронизация Kubernetes-манифестов",
    url: "https://argocd.alexshishin.ru",
    icon: Rocket,
    accent: "bg-sky-100 text-sky-600",
    credentials: { login: "jury", password: "jury_pass" },
  },
  {
    id: "mlflow",
    name: "MLflow",
    description: "Трекинг экспериментов и registry моделей",
    url: "https://mlflow.alexshishin.ru",
    icon: FlaskConical,
    accent: "bg-indigo-100 text-indigo-600",
    credentials: { login: "jury", password: "jury_pass_2026" },
  },
  {
    id: "airflow",
    name: "Airflow",
    description: "Оркестрация ML/ETL пайплайнов",
    url: "https://airflow.alexshishin.ru",
    icon: Workflow,
    accent: "bg-teal-100 text-teal-600",
    credentials: { login: "jury", password: "jury_pass" },
  },
  {
    id: "minio",
    name: "MinIO Console",
    description: "Артефакты и объектное хранилище моделей",
    url: "https://minio-console.alexshishin.ru",
    icon: Database,
    accent: "bg-rose-100 text-rose-600",
    credentials: { login: "jury", password: "jury_pass" },
  },
  {
    id: "grafana",
    name: "Grafana",
    description: "Метрики и дашборды инфраструктуры",
    url: "https://grafana.alexshishin.ru",
    icon: LineChart,
    accent: "bg-amber-100 text-amber-600",
    credentials: { login: "jury", password: "jury_pass" },
  },
];

export default function AnalyticsPage() {
  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-slate-100 px-4 py-4 sm:px-8 sm:py-6">
        <h1 className="font-sans text-xl font-extrabold text-slate-900">Аналитика интентов</h1>
        <p className="mt-1.5 text-sm text-slate-500">
          Инструменты и дашборды MLOps-платформы — метрики, эксперименты и деплои.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto p-4 sm:p-8">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {SERVICES.map((service) => (
            <ServiceTile key={service.id} service={service} />
          ))}
        </div>
      </div>
    </div>
  );
}
