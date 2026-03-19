CREATE OR REPLACE FUNCTION sync_user_role_name()
RETURNS TRIGGER AS $$
BEGIN
    -- Fetch the role_name from the roles table using the role_id
    SELECT role_name INTO NEW.role_name
    FROM roles
    WHERE role_id = NEW.role_id;

    -- Safety check: Ensure the role actually exists
    IF NEW.role_name IS NULL THEN
        RAISE EXCEPTION 'role_id % not found in roles table', NEW.role_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER trigger_sync_role_name
BEFORE INSERT OR UPDATE OF role_id ON user_roles
FOR EACH ROW
EXECUTE FUNCTION sync_user_role_name();