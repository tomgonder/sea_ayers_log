drop table if exists entries;
create table entries (
  id integer primary key autoincrement,
  date text not null,
  log_type text not null,
  aboard text not null,
  details text not null
);
