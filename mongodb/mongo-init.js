// Выполняется один раз при первом запуске контейнера
// Создаёт пользователя приложения с правами только на базу s3platform
 
db = db.getSiblingDB("s3platform");
 
db.createUser({
  user: "s3platform",
  pwd: "s3platform",
  roles: [{ role: "readWrite", db: "s3platform" }],
});
 
// Коллекция jobs с индексами
db.createCollection("jobs");
db.jobs.createIndex({ job_id: 1 }, { unique: true });
db.jobs.createIndex({ status: 1 });
db.jobs.createIndex({ created_at: -1 });
 
print("MongoDB init: база s3platform готова");