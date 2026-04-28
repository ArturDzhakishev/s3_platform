// Выполняется один раз при первом запуске контейнера
 
db = db.getSiblingDB("s3platform");
 
db.createUser({
  user: "s3platform",
  pwd: "s3platform",
  roles: [{ role: "readWrite", db: "s3platform" }],
});
 
// ── hosts ──────────────────────────────────────────────────────────────────
db.createCollection("hosts");
db.hosts.createIndex({ host_id: 1 },    { unique: true });
db.hosts.createIndex({ ip: 1 },         { unique: true });
db.hosts.createIndex({ status: 1 });
db.hosts.createIndex({ cluster_id: 1 }); // найти все хосты кластера
 
// ── clusters ───────────────────────────────────────────────────────────────
db.createCollection("clusters");
db.clusters.createIndex({ cluster_id: 1 }, { unique: true });
db.clusters.createIndex({ status: 1 });
db.clusters.createIndex({ engine: 1 });
db.clusters.createIndex({ created_at: -1 });
 
// ── jobs ───────────────────────────────────────────────────────────────────
db.createCollection("jobs");
db.jobs.createIndex({ job_id: 1 },     { unique: true });
db.jobs.createIndex({ cluster_id: 1 }); // история задач кластера
db.jobs.createIndex({ status: 1 });
db.jobs.createIndex({ created_at: -1 });
 
print("MongoDB init: коллекции hosts / clusters / jobs готовы");