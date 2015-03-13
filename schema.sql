drop table if exists a2a;
create table a2a (
aid1 text,
aid2 text,
w real not null default  0.00,
PRIMARY KEY (aid1, aid2)
);

drop table if exists a;
create table a (
aid text primary key,
display text
);
