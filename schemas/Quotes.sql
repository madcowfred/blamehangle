CREATE TABLE quotes (
    quote text NOT NULL,
    seen integer default 0,
    PRIMARY KEY (quote)
);
