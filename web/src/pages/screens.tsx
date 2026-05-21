/**
 * Feature-screen routes. Each is a stub until its plan phase delivers it
 * (see ScreenStub). Implemented screens replace their stub here.
 */
import { I } from "../components/icons";
import { ScreenStub } from "./ScreenStub";

export function Users() {
  return (
    <ScreenStub
      title="Users"
      phase="Phase 0"
      icon={<I.Users size={22} />}
      summary="Operator management — create and disable users, assign admin/user roles and reset passwords."
    />
  );
}
