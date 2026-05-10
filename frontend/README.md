# S3 Platform — Frontend

React + Vite + Tailwind CSS SPA для управления S3-кластерами.

## Страницы

| Путь | Страница |
|---|---|
| `/` | Dashboard — статистика + список кластеров + последние задачи |
| `/clusters` | Список кластеров + форма создания |
| `/clusters/:id` | Детали кластера, scale, история задач |
| `/jobs` | Все задачи с фильтром по статусу |
| `/jobs/:id` | Лог Ansible с подсветкой, auto-scroll |
| `/hosts` | Инвентарь хостов, ping |

## Запуск

```bash
# Установить зависимости
npm install

# Разработка (proxy → localhost:8000)
npm run dev
# http://localhost:3000

# Продакшен-сборка
npm run build
```

## Настройка под продакшен-сервер

```bash
# .env
VITE_BACKEND_URL=http://192.168.1.100:8000

npm run dev   # или npm run build
```

## Структура

```
src/
├── api/client.js          # все запросы к бэкенду
├── hooks/usePolling.js    # автообновление данных
├── components/
│   ├── Layout.jsx         # обёртка со Sidebar
│   ├── Sidebar.jsx        # навигация
│   ├── StatusBadge.jsx    # бейджи статусов
│   └── EngineBadge.jsx    # бейджи движков
└── pages/
    ├── Dashboard.jsx      # главная
    ├── Clusters.jsx       # список + форма создания
    ├── ClusterDetail.jsx  # детали + scale + удаление
    ├── Jobs.jsx           # список задач
    ├── JobDetail.jsx      # лог задачи
    └── Hosts.jsx          # инвентарь хостов
```
