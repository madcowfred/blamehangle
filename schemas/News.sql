CREATE TABLE news (
    title character varying(255) NOT NULL,
    url text,
    description text,
    added integer,
    PRIMARY KEY (title)
);
