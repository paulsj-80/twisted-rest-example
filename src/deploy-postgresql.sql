drop table if exists transactions;
drop table if exists accounts;
drop sequence if exists accounts_seq;

create sequence accounts_seq minvalue 10000000;
create table accounts (
       id int primary key default nextval('accounts_seq'),
       currency char(3) not null,
       balance decimal(10, 2) not null default 0.0,
       constraint balance_is_not_negative check (balance >= 0)
);
alter sequence accounts_seq owned by accounts.id;

create table transactions (
       id bigserial primary key,
       source_id int,
       dest_id int,
       amount decimal(10, 2) not null,

       constraint accounts_involved check (source_id is not null or dest_id is not null),
       constraint amount_positive check (amount > 0),
       constraint different_accounts check (source_id <> dest_id),

       foreign key (source_id) references accounts(id) on delete cascade,
       foreign key (dest_id) references accounts(id) on delete cascade
);

