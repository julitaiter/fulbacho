import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class GroupSelectionScreen extends StatelessWidget {
  const GroupSelectionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tus grupos'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Crear o unirse',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'La conexión real con Supabase debe usar las RPC public.create_group() y public.join_group_by_code().',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: <Widget>[
                      FilledButton(
                        onPressed: () => context.go('/group/demo-los-del-jueves'),
                        child: const Text('Crear grupo demo'),
                      ),
                      OutlinedButton(
                        onPressed: () => context.go('/group/demo-fulbito-miercoles'),
                        child: const Text('Unirse con código demo'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _GroupCard(
            title: 'Los del Jueves',
            subtitle: 'Código A9K3P2',
            onOpen: () => context.go('/group/demo-los-del-jueves'),
          ),
          const SizedBox(height: 12),
          _GroupCard(
            title: 'Fulbito Miércoles',
            subtitle: 'Código C7T5R4',
            onOpen: () => context.go('/group/demo-fulbito-miercoles'),
          ),
        ],
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  const _GroupCard({
    required this.title,
    required this.subtitle,
    required this.onOpen,
  });

  final String title;
  final String subtitle;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.arrow_forward),
        onTap: onOpen,
      ),
    );
  }
}
