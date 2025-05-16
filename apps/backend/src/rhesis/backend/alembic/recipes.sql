
-- Delete all test sets and prompts
delete from prompt_test_set;
delete from prompt_use_case;
delete from test_set;
delete from prompt;
delete from prompt_template;
delete from source;

-- Delete all test sets and prompts
delete from prompt_test_set;
delete from prompt_use_case;
delete from test_set;
delete from prompt;
--delete from prompt_template;
delete from topic where entity_type_id = '1a46ef32-2422-483e-930f-0e8e5206ec31';
delete from source where id <> '3953c187-20f1-4858-9052-6cd91549b9bd';
