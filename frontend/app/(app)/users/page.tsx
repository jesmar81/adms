"use client";

import { useCallback, useEffect, useState } from "react";
import { Pencil, Power, Save, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import { Can, useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import type { AdminUser, Company, CorporateGroup } from "@/types";

const COLUMNS: Column<AdminUser>[] = [
  {
    key: "scope",
    header: "Alcance",
    render: (u) => <span className="text-sm text-zinc-600">{u.is_superuser ? "Todos" : `${u.corporate_group_ids.length} grupo(s) · ${u.company_ids.length} empresa(s)`}</span>,
  },
  {
    key: "user",
    header: "Usuario",
    render: (u) => (
      <span>
        <span className="block font-medium">{u.username}</span>
        <span className="mt-0.5 block text-[13px] text-zinc-500">{u.email}</span>
      </span>
    ),
  },
  {
    key: "roles",
    header: "Roles",
    render: (u) =>
      u.roles.length > 0 ? (
        <span className="flex flex-wrap gap-1.5">
          {u.roles.map((r) => (
            <Badge key={r} tone="zinc">
              {r}
            </Badge>
          ))}
        </span>
      ) : (
        <span className="text-zinc-500">—</span>
      ),
  },
  {
    key: "active",
    header: "Activo",
    render: (u) => <Badge tone={u.is_active ? "emerald" : "red"}>{u.is_active ? "Sí" : "No"}</Badge>,
  },
  {
    key: "super",
    header: "Superusuario",
    render: (u) => <span className="text-zinc-600">{u.is_superuser ? "Sí" : "No"}</span>,
  },
];

export default function Page() {
  const { user: currentUser } = useAuth();
  const { notify } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [groups, setGroups] = useState<CorporateGroup[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleName, setRoleName] = useState("viewer");
  const [groupIds, setGroupIds] = useState<string[]>([]);
  const [companyIds, setCompanyIds] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [editRoleName, setEditRoleName] = useState("viewer");
  const [editGroupIds, setEditGroupIds] = useState<string[]>([]);
  const [editCompanyIds, setEditCompanyIds] = useState<string[]>([]);
  const [savingEdit, setSavingEdit] = useState(false);
  const delegableGroups = currentUser?.is_superuser
    ? groups
    : groups.filter((group) => currentUser?.corporate_group_ids.includes(group.id));

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await api.users());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void Promise.all([api.corporateGroups(), api.companies()]).then(([loadedGroups, loadedCompanies]) => {
      setGroups(loadedGroups);
      setCompanies(loadedCompanies);
    }).catch(setError);
  }, [load]);

  async function create() {
    if (creating) return;
    setCreating(true);
    try {
      await api.createUser({
        username: username.trim(),
        email: email.trim(),
        password,
        role_names: [roleName],
        corporate_group_ids: groupIds,
        company_ids: companyIds,
      });
      notify(`Usuario ${username.trim()} creado`, { tone: "success" });
      setUsername("");
      setEmail("");
      setPassword("");
      setRoleName("viewer");
      setGroupIds([]);
      setCompanyIds([]);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(u: AdminUser) {
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      notify(u.is_active ? `Usuario ${u.username} deshabilitado` : `Usuario ${u.username} habilitado`, {
        tone: "success",
      });
      await load();
    } catch (err) {
      setError(err);
    }
  }

  function openEdit(u: AdminUser) {
    setEditing(u);
    setEditRoleName(u.roles[0] ?? "viewer");
    setEditGroupIds(u.corporate_group_ids);
    setEditCompanyIds(u.company_ids);
  }

  async function saveEdit() {
    if (!editing || savingEdit) return;
    setSavingEdit(true);
    try {
      await api.updateUser(editing.id, {
        role_names: [editRoleName],
        corporate_group_ids: editGroupIds,
        company_ids: editCompanyIds,
      });
      notify(`Alcance de ${editing.username} actualizado`, { tone: "success" });
      setEditing(null);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSavingEdit(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    try {
      await api.deleteUser(pendingDelete.id);
      notify(`Usuario ${pendingDelete.username} deshabilitado`, { tone: "success" });
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Usuarios"
        description="Cuentas de acceso a la plataforma. La eliminación deshabilita la cuenta, nunca la borra."
        crumbs={[{ label: "Usuarios" }]}
      />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}

      <Can permission="users.write">
        <Card className="mb-4 p-5">
          <h2 className="text-[15px] font-semibold tracking-tight">Crear usuario</h2>
          <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
            <Field label="Usuario">
              {(id) => (
                <Input id={id} placeholder="Nombre de usuario" value={username} onChange={(e) => setUsername(e.target.value)} />
              )}
            </Field>
            <Field label="Correo">
              {(id) => (
                <Input id={id} type="email" placeholder="usuario@ejemplo.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              )}
            </Field>
            <Field label="Contraseña" hint="Mínimo 15 caracteres">
              {(id) => (
                <Input id={id} type="password" placeholder="••••••••••" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
              )}
            </Field>
            <Field label="Rol">
              {(id) => <Select id={id} value={roleName} onChange={(event) => setRoleName(event.target.value)}><option value="viewer">Consulta</option><option value="operator">Operación</option>{currentUser?.is_superuser ? <><option value="hr">Recursos humanos</option><option value="director">Dirección</option><option value="admin">Administración</option></> : null}</Select>}
            </Field>
            <div className="sm:col-span-2 xl:col-span-4">
              <p className="text-[13px] font-medium text-zinc-700">Grupos completos</p>
              <div className="mt-2 flex flex-wrap gap-2">{delegableGroups.map((group) => <label key={group.id} className="flex cursor-pointer items-center gap-2 rounded-full border border-line-soft px-3 py-2 text-sm"><input type="checkbox" checked={groupIds.includes(group.id)} onChange={(event) => setGroupIds((current) => event.target.checked ? [...current, group.id] : current.filter((id) => id !== group.id))} />{group.name}</label>)}</div>
            </div>
            <div className="sm:col-span-2 xl:col-span-4">
              <p className="text-[13px] font-medium text-zinc-700">Empresas específicas</p>
              <p className="mt-0.5 text-xs text-zinc-500">Úsalo para limitar a una empresa sin conceder todo su grupo.</p>
              <div className="mt-2 flex flex-wrap gap-2">{companies.filter((company) => !groupIds.includes(company.corporate_group_id)).map((company) => <label key={company.id} className="flex cursor-pointer items-center gap-2 rounded-full border border-line-soft px-3 py-2 text-sm"><input type="checkbox" checked={companyIds.includes(company.id)} onChange={(event) => setCompanyIds((current) => event.target.checked ? [...current, company.id] : current.filter((id) => id !== company.id))} />{company.legal_name}</label>)}</div>
            </div>
            <div className="flex items-end xl:col-span-4">
              <Button variant="primary" onClick={() => void create()} loading={creating}>
                Crear usuario
              </Button>
            </div>
          </div>
        </Card>
      </Can>

      {loading ? (
        <LoadingState rows={5} />
      ) : (
        <DataTable
          ariaLabel="Usuarios de la aplicación"
          columns={[
            ...COLUMNS,
            {
              key: "actions",
              header: "",
              render: (u) => (
                <span className="flex justify-end gap-1">
                  <Can permission="users.write">
                    <Button size="sm" variant="ghost" icon={<Pencil className="h-4 w-4" />} className="w-8 !px-0" aria-label={`Editar acceso de ${u.username}`} title="Editar acceso y alcance" onClick={() => openEdit(u)} />
                    <Button size="sm" variant="ghost" icon={<Power className="h-4 w-4" />} className="w-8 !px-0" aria-label={u.is_active ? `Deshabilitar ${u.username}` : `Habilitar ${u.username}`} title={u.is_active ? "Deshabilitar" : "Habilitar"} onClick={() => void toggleActive(u)} />
                  </Can>
                  <Can permission="users.delete">
                    <Button size="sm" variant="ghost" icon={<Trash2 className="h-4 w-4" />} className="w-8 !px-0 text-red-600" aria-label={`Eliminar ${u.username}`} title="Deshabilitar definitivamente" onClick={() => setPendingDelete(u)} />
                  </Can>
                </span>
              ),
            },
          ]}
          data={users}
          keyOf={(u) => u.id}
          renderCard={(u) => (
            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="truncate text-sm font-medium">{u.username}</p>
                <Badge tone={u.is_active ? "emerald" : "red"}>{u.is_active ? "Activo" : "Inactivo"}</Badge>
              </div>
              <p className="mt-0.5 truncate text-[13px] text-zinc-500">{u.email}</p>
              <div className="mt-2.5 flex gap-1">
                <Can permission="users.write">
                  <Button size="sm" variant="ghost" icon={<Pencil className="h-4 w-4" />} className="w-8 !px-0" aria-label={`Editar acceso de ${u.username}`} title="Editar acceso y alcance" onClick={() => openEdit(u)} />
                  <Button size="sm" variant="ghost" icon={<Power className="h-4 w-4" />} className="w-8 !px-0" aria-label={u.is_active ? `Deshabilitar ${u.username}` : `Habilitar ${u.username}`} title={u.is_active ? "Deshabilitar" : "Habilitar"} onClick={() => void toggleActive(u)} />
                </Can>
                <Can permission="users.delete">
                  <Button size="sm" variant="ghost" icon={<Trash2 className="h-4 w-4" />} className="w-8 !px-0 text-red-600" aria-label={`Eliminar ${u.username}`} title="Deshabilitar definitivamente" onClick={() => setPendingDelete(u)} />
                </Can>
              </div>
            </div>
          )}
          empty={<EmptyState title="Sin usuarios" description="Aún no hay cuentas registradas." />}
        />
      )}

      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Deshabilitar usuario"
        description={`La cuenta ${pendingDelete?.username ?? ""} perderá el acceso, pero su historial se conserva.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancelar
            </Button>
            <Button variant="danger" onClick={() => void confirmDelete()} loading={deleting}>
              Deshabilitar
            </Button>
          </>
        }
      >
        <p className="text-sm text-zinc-500">Esta acción puede revertirse volviendo a habilitar la cuenta.</p>
      </Modal>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title="Acceso y alcance"
        description={`Define qué puede administrar ${editing?.username ?? ""}. Los cambios quedan auditados.`}
        footer={<><Button variant="ghost" icon={<X className="h-4 w-4" />} className="w-10 !px-0" aria-label="Cancelar" title="Cancelar" onClick={() => setEditing(null)} /><Button variant="primary" icon={<Save className="h-4 w-4" />} className="w-10 !px-0" aria-label="Guardar acceso" title="Guardar acceso" onClick={() => void saveEdit()} loading={savingEdit} /></>}
      >
        <div className="grid gap-4">
          <Field label="Rol">{(id) => <Select id={id} value={editRoleName} onChange={(event) => setEditRoleName(event.target.value)}><option value="viewer">Consulta</option><option value="operator">Operación</option>{currentUser?.is_superuser ? <><option value="hr">Recursos humanos</option><option value="director">Dirección</option><option value="admin">Administración</option></> : null}</Select>}</Field>
          <div>
            <p className="text-[13px] font-medium text-zinc-700">Grupos completos</p>
            <div className="mt-2 flex flex-wrap gap-2">{delegableGroups.map((group) => <label key={group.id} className="flex cursor-pointer items-center gap-2 rounded-full border border-line-soft px-3 py-2 text-sm"><input type="checkbox" checked={editGroupIds.includes(group.id)} onChange={(event) => setEditGroupIds((current) => event.target.checked ? [...current, group.id] : current.filter((id) => id !== group.id))} />{group.name}</label>)}</div>
          </div>
          <div>
            <p className="text-[13px] font-medium text-zinc-700">Empresas específicas</p>
            <p className="mt-0.5 text-xs text-zinc-500">Otorga acceso sólo a la empresa elegida, sin extenderlo a sus empresas hermanas.</p>
            <div className="mt-2 flex flex-wrap gap-2">{companies.filter((company) => !editGroupIds.includes(company.corporate_group_id)).map((company) => <label key={company.id} className="flex cursor-pointer items-center gap-2 rounded-full border border-line-soft px-3 py-2 text-sm"><input type="checkbox" checked={editCompanyIds.includes(company.id)} onChange={(event) => setEditCompanyIds((current) => event.target.checked ? [...current, company.id] : current.filter((id) => id !== company.id))} />{company.legal_name}</label>)}</div>
          </div>
        </div>
      </Modal>
    </>
  );
}
