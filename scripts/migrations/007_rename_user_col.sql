ALTER TABLE user_profiles RENAME COLUMN skills_languages TO skills;
ALTER TABLE user_profiles DROP COLUMN skills_frameworks;
ALTER TABLE user_profiles DROP COLUMN skills_cloud;