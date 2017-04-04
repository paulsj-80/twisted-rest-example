drop table if exists transactions;
drop table if exists accounts;


create table accounts (
       id int(8) not null auto_increment,
       currency char(3) not null,
       balance decimal(10, 2) not null default 0.0,
       unique key (id),
       constraint balance_is_not_negative check (balance >= 0)
) engine=innodb auto_increment=10000000;

create table transactions (
       id int(11) not null auto_increment,
       source_id int(8),
       dest_id int(8),
       amount decimal(10, 2) not null,

       constraint accounts_involved check (source_id is not null or dest_id is not null),
       constraint amount_positive check (amount > 0),
       constraint different_accounts check (source_id <> dest_id),

       foreign key (source_id) references accounts(id) on delete cascade,
       foreign key (dest_id) references accounts(id) on delete cascade,
       unique key (id)
) engine=innodb;

